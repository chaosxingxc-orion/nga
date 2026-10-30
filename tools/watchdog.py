#!/usr/bin/env python3
"""Tier-0 experiment watchdog: a deterministic script, no model, standard library only.

Scans run roots, classifies each run from its terminal marker and heartbeat, summarizes progress,
clusters warning/error lines into signatures, flags suspicious (perfect-by-construction) metrics in
report.json, and writes a small, bounded digest.json + digest.md. See tools/README.md.

Run with:  python3 -P tools/watchdog.py [--root DIR ...] [--out-dir DIR] [--watch --interval 60]
"""
import argparse
import calendar
import errno
import fcntl
import fnmatch
import glob
import hashlib
import json
import math
import os
import re
import signal
import socket
import sys
import tempfile
import time

DEFAULT_ROOT = "/mnt/cephfs/xingchao/experiments/jev/"
STATE_RANK = {"archived": -1, "done": 0, "running": 1, "unknown": 2, "stalled": 3, "failed": 4}
EXIT_CODES = {"archived": 0, "done": 0, "running": 10, "unknown": 20, "stalled": 30, "failed": 40}
EXIT_NO_RUNS = 20
WATCH_FILE = "WATCH.json"
TIER_NAMES = ("fast", "medium", "slow")
MIN_INTERVAL = 600.0       # floor for the --watch tick, unless --allow-fast-poll
INFER_WINDOW = 20          # most recent heartbeat samples used to infer the period
INFER_MIN_GAPS = 1         # positive gaps needed to infer at all (none: fall back to medium)
INFER_MEDIAN_GAPS = 3      # with fewer gaps than this use the MAX gap (err long), from this many on the median
CHUNK = 8 << 20
MAX_LINE = 4000
MAX_CARRY = 1 << 20

TS_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:[.,]\d+)?(Z|[+-]\d{2}:?\d{2})?")


# ----------------------------------------------------------------------------- configuration
def build_parser():
    p = argparse.ArgumentParser(prog="watchdog.py", description=__doc__.split("\n\n")[0])
    a = p.add_argument
    a("--root", action="append", help="run root to scan (repeatable); default %s" % DEFAULT_ROOT)
    a("--out-dir", help="where digest.json/digest.md go; default <first root>/_watchdog")
    a("--stall-seconds", type=float, default=None,
      help="GLOBAL override of the per-run stall threshold (default: none; the threshold comes from each run's tier)")
    for name, rc, st in (("fast", 600, 600), ("medium", 1200, 1800), ("slow", 3600, 7200)):
        a("--%s-recheck" % name, type=float, default=float(rc), help="%s tier: re-read the run this often (default %d s)" % (name, rc))
        a("--%s-stall" % name, type=float, default=float(st), help="%s tier: heartbeat older than this => stalled (default %d s)" % (name, st))
    a("--flat-multiple", type=float, default=2.0,
      help="running run whose progress count is unchanged for this x its stall threshold, with a fresh heartbeat, is flagged (default 2)")
    a("--deadline-hours", type=float, default=48.0,
      help="a run with a declared total whose OPTIMISTIC finish estimate is further away than this is flagged (default 48)")
    a("--stall-multiple", type=float, default=5.0,
      help="inferred runs: stall threshold = this x the median heartbeat gap (default 5)")
    a("--stall-floor", type=float, default=600.0, help="inferred runs: the stall threshold is never below this (default 600 s)")
    a("--clock-skew-seconds", type=float, default=120.0, help="heartbeat further in the future than this => unknown")
    a("--window-seconds", type=float, default=900.0, help="throughput window (default 900)")
    a("--archive-seconds", type=float, default=21600.0,
      help="no marker, no heartbeat file, newest log older than this => archived, escalation none (default 21600 = 6h)")
    a("--why-names", default="WHY_STOPPED.json,WHY_FAILED.json",
      help="files whose note is surfaced in the digest as one short line")
    a("--max-depth", type=int, default=4, help="directory depth below a root to look for runs (default 4)")
    a("--marker-names", default="DONE,FAILED,exit_code,EXIT_CODE,EVAL_COMPLETE.json,K0_COMPLETE.json",
      help="terminal marker file names (plain text or a JSON object with an integer exit_code)")
    a("--heartbeat-name", default="heartbeat.log")
    a("--log-globs", default="*.log,logs/*.log", help="log files in a run dir; also <rundir>.*log beside the dir")
    a("--report-name", default="report.json")
    a("--skip-dirs", default="readouts,kernel_meta,__pycache__,node_modules")
    a("--max-signatures", type=int, default=8, help="error signatures reported per run (default 8)")
    a("--max-tracked", type=int, default=500, help="distinct signatures tracked per run before counting overflow")
    a("--exemplar-width", type=int, default=160)
    a("--ctx-before", type=int, default=10, help="exemplar pointer: lines before the matching line")
    a("--ctx-after", type=int, default=3, help="exemplar pointer: lines after the matching line")
    a("--ignore", default=r"(?i)\b(?:no|0|zero) (?:errors?|warnings?|failures?)\b|\b(?:error|errors|warnings?|failed|failures?)\s*[=:]\s*0\b|['\"]errors?['\"]\s*[,:]",
      help="regex; matching lines are not counted as warnings/errors")
    a("--max-md-bytes", type=int, default=16000, help="hard cap on digest.md size in bytes (default 16000); sections are dropped by priority")
    a("--min-n", type=int, default=30, help="cells with a sample count below this are flagged (default 30)")
    a("--min-cells", type=int, default=3, help="a table needs at least this many cells for the identical-metric check")
    a("--suppress-roles", default="constant,uniform,mock-*",
      help="comma list of fnmatch patterns; a report path segment matching one marks expected-degenerate values "
           "(exact 0/1, identical across cells) as suppressed and counted, not flagged")
    a("--protect-roles", default="primary,empty_input,question_only",
      help="path segments that are never suppressed, even below a suppressed one")
    a("--no-suppress", action="store_true", help="turn suppression off wholesale: flag everything")
    a("--max-flags-per-kind", type=int, default=5, help="suspicious items listed per run and kind")
    a("--rate-keys", default=r"(?i)(?:^|[^a-z])(rate|acc|prec|recall|f1|auc|agree|consist|flip|score|readout|overall|share|constant|growth|ece)",
      help="regex marking a JSON key (leaf or up to 2 ancestors) as a rate/accuracy-like metric")
    a("--count-keys", default=r"^(n|n_units|n_items|n_samples|n_rows|count|samples|num_samples)$",
      help="regex for sample-count keys")
    a("--watch", action="store_true", help="loop forever, rewriting the digest in place")
    a("--interval", type=float, default=MIN_INTERVAL,
      help="seconds between watch ticks (default 600, also the minimum unless --allow-fast-poll). Each run is re-read only "
           "when its own tier cadence is due")
    a("--allow-fast-poll", action="store_true", help="permit --watch --interval below %d s (tests, debugging)" % MIN_INTERVAL)
    a("--perf-depth", type=int, default=2,
      help="directory levels below a run to look in for throughput sources (heartbeat.log, perf.json, progress.log); default 2, "
           "so run/res/p0/heartbeat.log is found")
    a("--perf-regress-ratio", type=float, default=0.7,
      help="a running run whose windowed rate is below this x its DECLARED baseline (perf.json) is flagged (default 0.7)")
    a("--perf-ratio-key", choices=("tok_s", "q_s"), default="tok_s",
      help="which perf.json ratio decides the regression flag: tokens/s (default) or questions/s; both are shown")
    a("--queued-names", default="QUEUED",
      help="a run directory holding one of these files, with no terminal marker and no heartbeat file, counts as queued (default QUEUED)")
    a("--no-npu", action="store_true", default=os.environ.get("WATCHDOG_NO_NPU", "") not in ("", "0"),
      help="do not look at NPU utilisation (no ssh); also set by the environment variable WATCHDOG_NO_NPU")
    a("--npu-host", default="npu", help="ssh host that runs npu-smi (default npu); 'local' runs the command on this host")
    a("--npu-samples", type=int, default=4, help="npu-smi snapshots per pass (default 4)")
    a("--npu-sample-gap", type=float, default=3.0, help="seconds between snapshots (default 3)")
    a("--npu-timeout", type=float, default=45.0, help="give up on the whole ssh call after this many seconds (default 45)")
    a("--npu-low-pct", type=float, default=30.0, help="a claimed chip below this mean AICore %% is shown as low, informational only (default 30)")
    a("--npu-window-seconds", type=float, default=3600.0,
      help="the utilisation verdict (low / busy) is the mean AICore over the claimed passes of this trailing window (default 3600 = 1 h: "
           "about six 10-minute passes of four snapshots, long enough to average out the 14-94%% swings a bursty eval shows within "
           "seconds, short enough that an idle stretch hours ago cannot colour it); the digest states the window and the passes it had")
    a("--npu-min-passes", type=int, default=3,
      help="a claimed chip with fewer passes than this in the window is reported 'unknown', never 'low' (default 3)")
    a("--chip-allocation", default=None,
      help="CHIP-ALLOCATION.json, the source of truth for who OWNS a chip (default <first root>/CHIP-ALLOCATION.json). Read only. Ownership comes "
           "only from this file, never from a sample; missing or unparseable means 'ownership unknown', never 'free'")
    a("--npu-history-from", default=None,
      help="read npu_history.json from this directory (e.g. the daemon's _watchdog/) instead of --out-dir, read only, so a one-shot pass "
           "into a scratch --out-dir has the same utilisation window as the daemon")
    a("--npu-owned-idle-seconds", type=float, default=1800.0,
      help="an OWNED chip with no resident process for at least this long (and --npu-owned-idle-passes consecutive passes) escalates to "
           "'decide': a forgotten release or a dead job. Default 1800 s = 30 min: a chip between shards or loading a checkpoint is idle for "
           "seconds to a few minutes (the 04:37Z incident was one such gap), so 30 min is several times the longest legitimate gap seen, "
           "equals the medium-tier stall threshold, and is still short against a multi-hour round")
    a("--npu-owned-idle-passes", type=int, default=3,
      help="... and seen idle in at least this many consecutive passes (default 3; at the 10-minute tick the seconds condition then needs 4)")
    a("--npu-idle-hbm-mb", type=float, default=4096.0,
      help="a chip with no resident process and at most this much HBM has no process (the driver baseline is about 3450 MB; default 4096)")
    a("--npu-near-zero-pct", type=float, default=5.0, help="a claimed chip whose every snapshot is at or below this %% AICore is quiet (default 5)")
    a("--npu-wedged-passes", type=int, default=3, help="a claimed chip quiet for at least this many consecutive passes ... (default 3)")
    a("--npu-wedged-seconds", type=float, default=1200.0,
      help="... spanning at least this long is flagged as possibly wedged (default 1200 = 20 min; loading a checkpoint is legitimately quiet)")
    a("--obligations", action="append",
      help="obligations file (repeatable); default <root>/obligations.json for every root. Declares outstanding products, see tools/README.md")
    a("--no-retain", action="store_true", help="do not keep dated copies of flagged passes under <out-dir>/_retained/")
    a("--retain-max", type=int, default=60, help="keep at most this many retained copies (digest.json + digest.md pair), oldest deleted first (default 60)")
    a("--retain-max-mb", type=float, default=200.0, help="and at most this many MB in total (default 200)")
    a("--retain-flap-seconds", type=float, default=3600.0,
      help="a flag that reappears within this long of its last retention is not 'new' (default 3600)")
    a("--retain-refresh-hours", type=float, default=6.0,
      help="while any flag is present, re-capture when the newest retained copy is older than this (default 6)")
    a("--print", dest="print_md", action="store_true", help="also print digest.md to stdout")
    return p


def make_cfg(**kw):
    cfg = build_parser().parse_args([])
    for k, v in kw.items():
        if not hasattr(cfg, k):
            raise AttributeError(k)
        setattr(cfg, k, v)
    if not cfg.root:
        cfg.root = [DEFAULT_ROOT]
    if not cfg.out_dir:
        cfg.out_dir = os.path.join(os.path.abspath(cfg.root[0]), "_watchdog")
    cfg.out_dir = os.path.abspath(cfg.out_dir)
    cfg.markers = [x for x in cfg.marker_names.split(",") if x]
    cfg.globs = [x for x in cfg.log_globs.split(",") if x]
    cfg.why_files = [x for x in cfg.why_names.split(",") if x]
    cfg.skip = set(x for x in cfg.skip_dirs.split(",") if x)
    cfg.ignore_re = re.compile(cfg.ignore) if cfg.ignore else None
    cfg.suppress_pats = [] if cfg.no_suppress else [x for x in cfg.suppress_roles.split(",") if x]
    cfg.protect_set = set(x for x in cfg.protect_roles.split(",") if x)
    cfg.tiers = {n: {"recheck_s": getattr(cfg, n + "_recheck"), "stall_s": getattr(cfg, n + "_stall")} for n in TIER_NAMES}
    cfg.queued_files = [x for x in cfg.queued_names.split(",") if x]
    cfg.rate_re = re.compile(cfg.rate_keys)
    cfg.count_re = re.compile(cfg.count_keys)
    return cfg


# ----------------------------------------------------------------------------- small helpers
def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts is not None else None


def parse_ts(m):
    """Regex match of TS_RE -> epoch seconds. Naive timestamps are taken as UTC."""
    y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
    try:
        t = calendar.timegm((y, mo, d, h, mi, s))
    except (ValueError, OverflowError):
        return None
    tz = m.group(7)
    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        digits = tz[1:].replace(":", "")
        t -= sign * (int(digits[:2]) * 3600 + int(digits[2:4]) * 60)
    return float(t)


def human_age(sec):
    if sec is None:
        return "-"
    sec = int(sec)
    if sec < 0:
        return "-%ds" % -sec
    if sec < 90:
        return "%ds" % sec
    if sec < 5400:
        return "%dm" % round(sec / 60)
    if sec < 172800:
        return "%.1fh" % (sec / 3600)
    return "%dd" % (sec // 86400)


def atomic_write(path, text):
    """Write temp file in the same directory, fsync, rename. A reader sees the old or the new file, never a mix."""
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix="." + os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ----------------------------------------------------------------------------- error signatures
_SUBS = [
    (TS_RE, "<ts>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    (re.compile(r"\b0[xX][0-9a-fA-F]+\b"), "<hex>"),
    (re.compile(r"(?:(?<=^)|(?<=[\s'\"=(\[,:]))/[\w.\-+@%]+(?:/[\w.\-+@%]*)*"), "<path>"),
    (re.compile(r"(?<![\w/:<])(?:[\w.\-]+/)+[\w\-]+\.\w+"), "<path>"),
    (re.compile(r"(?i)\b(pid|tid|process)\b[\s=:#]*\d+"), r"\1 <pid>"),
    (re.compile(r"\b[0-9a-f]{12,}\b"), "<id>"),
    (re.compile(r"(?<![A-Za-z0-9_])(shard|rank|worker|npu|gpu|cuda|cpu|device|node|core|thread|proc|task|step|epoch|attempt|"
                r"batch|chunk|layer|item|run|job|pid|tid)_?\d+(?![A-Za-z0-9_])", re.I), r"\1<n>"),   # shard3, npu0, rank12
    (re.compile(r"(?<![A-Za-z0-9_<])\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\d_>])"), "<n>"),
    (re.compile(r"\s+"), " "),
]


_SECRET = re.compile(r"(?i)(://)[^/\s@]+@|\b((?:\w*(?:token|passw(?:or)?d|secret|api[_-]?key|credential)\w*)\s*[=:]\s*)\S+")


def redact(text):
    """Exemplars go into a digest others read: never carry credentials (proxy URLs, tokens) into it."""
    return _SECRET.sub(lambda m: (m.group(1) + "***@") if m.group(1) else (m.group(2) + "***"), text)


def normalize(line):
    """Signature of a log line: timestamps, hex addresses, uuids, PIDs, absolute paths, line numbers and bare
    integers are replaced by placeholders. Codes such as E40021 or error names are kept, so different failures
    stay apart while the same failure on shard3 and shard4 groups together."""
    s = line
    for rx, rep in _SUBS:
        s = rx.sub(rep, s)
    return s.strip()[:200]


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\[\d{1,3}(?:;\d{1,3})*m(?=\()")
HARD_RE = re.compile(
    r"\b(error|errors|fatal|critical|exception|traceback|panic|oom|out of memory|killed|segmentation fault|"
    r"aborted|assertion)\b|\b\w*(?:Error|Exception)\b", re.I)
WARN_RE = re.compile(r"\bwarn(?:ing|ings)?\b|\b\w*Warning\b", re.I)
SOFT_RE = re.compile(r"\b(failed|failure|failures)\b", re.I)


# Phrases that contain an error word but are a run's own record of a deliberate act, not a failure. Each pattern is removed from the line
# BEFORE the error-word test, so it can silence only its own span: any other error word on the same line still counts, and a line that
# merely says "killed" or "FAILED" elsewhere is unaffected. The qualifier must be written by the run itself in the line:
#   "killed (disarmed|deliberate|intentional)"  a process the run's own launcher stopped on purpose (k0_fp32/join.log, 2026-10-30)
#   "waiting for <path>/DONE (or FAILED)"        FAILED here is the name of a marker file the run is waiting for, not an outcome
BENIGN_SPANS = [
    re.compile(r"\bkilled\s*\(\s*(?:disarmed|deliberate|deliberately|intentional|intentionally)\s*\)", re.I),
    re.compile(r"\bwaiting\s+for\s+\S*/(?:DONE|exit_code|EXIT_CODE)\s*\(or\s+FAILED\)", re.I),
]


def classify_line(seg, cfg):
    """'error' | 'warning' | None. A line that says 'warning' and carries no hard error word is a warning
    even if it also says 'failed' (e.g. 'UserWarning: Failed to create processor')."""
    if cfg.ignore_re is not None and cfg.ignore_re.search(seg):
        return None
    for rx in BENIGN_SPANS:
        seg = rx.sub(" ", seg)
    if WARN_RE.search(seg) and not re.search(r"\b(?:traceback|fatal|critical|panic|segmentation fault)\b", seg, re.I) \
            and not re.search(r"\b\w*(?:Error|Exception)\b", ANSI_RE.sub("", seg).replace("Warning", "")):
        return "warning"
    if HARD_RE.search(seg) or SOFT_RE.search(seg):
        return "error"
    return None


class Sig:
    __slots__ = ("sig", "sev", "count", "first_ts", "last_ts", "ex_line", "ex_byte", "ex_text", "last_line")


class LogState:
    """Incremental scan state for one log file (kept across passes in --watch mode)."""

    def __init__(self):
        self.inode = None
        self.offset = 0
        self.lineno = 0
        self.sigs = {}
        self.dropped = 0

    def reset(self, inode):
        self.__init__()
        self.inode = inode


def _process(body, base, st, cfg):
    pos = base
    for raw in body.split(b"\n")[:-1]:
        line_start = pos
        pos += len(raw) + 1
        st.lineno += 1
        text = raw.decode("utf-8", "replace")
        if len(text) > MAX_LINE:
            text = text[:MAX_LINE]
        segs = text.split("\r") if "\r" in text else (text,)
        for seg in segs:
            seg = redact(ANSI_RE.sub("", seg)).strip()
            if not seg:
                continue
            sev = classify_line(seg, cfg)
            if not sev:
                continue
            sig = normalize(seg)
            e = st.sigs.get(sig)
            m = TS_RE.search(seg)
            ts = parse_ts(m) if m else None
            if e is None:
                if len(st.sigs) >= cfg.max_tracked:
                    st.dropped += 1
                    continue
                e = Sig()
                e.sig, e.sev, e.count = sig, sev, 0
                e.first_ts = e.last_ts = None
                e.ex_line, e.ex_byte, e.ex_text = st.lineno, line_start, seg
                st.sigs[sig] = e
            e.count += 1
            e.last_line = st.lineno
            if ts is not None:
                if e.first_ts is None:
                    e.first_ts = ts
                e.last_ts = ts


def scan_log(path, st, cfg, now):
    try:
        s = os.stat(path)
    except OSError:
        return
    if st.inode != s.st_ino or s.st_size < st.offset:
        st.reset(s.st_ino)
    try:
        f = open(path, "rb")
    except OSError:
        return
    with f:
        f.seek(st.offset)
        carry = b""
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            data = carry + chunk
            cut = data.rfind(b"\n")
            if cut < 0:
                carry = data
                if len(carry) > MAX_CARRY:
                    _process(carry + b"\n", st.offset, st, cfg)
                    st.offset += len(carry)
                    carry = b""
                continue
            body, carry = data[:cut + 1], data[cut + 1:]
            _process(body, st.offset, st, cfg)
            st.offset += len(body)
        # A last line without newline counts once the file has been quiet for a while (killed process).
        if carry and now - s.st_mtime > 30:
            _process(carry + b"\n", st.offset, st, cfg)
            st.offset += len(carry)


# ----------------------------------------------------------------------------- heartbeat / progress
_PAIR = re.compile(r"([A-Za-z][\w@.+\-]*)=(\d+)")
_SHARDS = re.compile(r"alive_shards=(\d+)/(\d+)")
_FRAC = re.compile(r"(?<![\w.])(\d+)\s*/\s*(\d+)(?![\w.])")
_DONE = re.compile(r"\b(?:done|completed|processed|items|n_done|step)\s*[=:]\s*(\d+)", re.I)
_TOTAL = re.compile(r"\b(?:total|n_total|of)\s*[=:]?\s*(\d+)", re.I)


_NUM = r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
_PERF_RATE = re.compile(r"\b(tok|ex|q)_s_(chip|host_nochip)(?:_w(\d+))?=(%s)(?![\w.])" % _NUM)
_PERF_AUX = re.compile(r"\b(chips|procs_on_chip|reserved_gib|step_s)=(%s)(?![\w.])" % _NUM)
_CHIP_ID = re.compile(r"\bchip=(\d+)(?![\w.])")     # a worker names the chip it runs on; "chips=" (a count) does not match


def parse_perf_fields(text):
    """Throughput fields of one heartbeat line, or None. Key names carry the scope, which is never relabelled:
    tok_s_chip_w20 / q_s_chip_w20 / ex_s_chip_w20 are per chip; tok_s_host_nochip_w20 / ex_s_host_nochip_w20 are HOST rates of a run
    with no chip (chips=0, a CPU run). Aux keys: chips, procs_on_chip, reserved_gib, step_s."""
    rates = {}
    for m in _PERF_RATE.finditer(text):
        kind, scope, w, v = m.groups()
        rates[kind] = (float(v), "host" if scope == "host_nochip" else "chip", int(w) if w else None)
    if not rates:
        return None
    out = {"tok_s": None, "ex_s": None, "ex_unit": None, "scope": None, "window": None, "chips": None,
           "procs_on_chip": None, "reserved_gib": None, "step_s": None, "chip_id": None}
    cm = _CHIP_ID.search(text)
    if cm:
        out["chip_id"] = int(cm.group(1))
    scopes = set()
    for kind, (v, sc, w) in rates.items():
        scopes.add(sc)
        out["window"] = w if w else out["window"]
        if kind == "tok":
            out["tok_s"] = v
        else:
            out["ex_s"], out["ex_unit"] = v, kind
    out["scope"] = scopes.pop() if len(scopes) == 1 else "mixed"
    for k, v in _PERF_AUX.findall(text):
        out[{"chips": "chips", "procs_on_chip": "procs_on_chip", "reserved_gib": "reserved_gib", "step_s": "step_s"}[k]] = \
            int(float(v)) if k in ("chips", "procs_on_chip") else float(v)
    return out


def parse_heartbeat_line(line):
    m = TS_RE.search(line)
    if not m:
        return None
    ts = parse_ts(m)
    if ts is None:
        return None
    rest = line[m.end():]
    done = total = None
    counters = {}
    fields = {}
    if "rows:" in rest:
        head, tail = rest.split("rows:", 1)
        fields = {k: int(v) for k, v in _PAIR.findall(head)}
        sm = _SHARDS.search(head)
        if sm:
            fields["shards_total"] = int(sm.group(2))
        counters = {k: int(v) for k, v in _PAIR.findall(tail)}
        # A line with a rows: section is explicit: progress is the sum of its counters, and an empty section is zero rows.
        # It must never fall through to the N/M matcher, which would read alive_shards=6/6 as "6 of 6 done".
        done = sum(counters.values())
    if done is None:
        fm = _FRAC.search(rest)
        if fm:
            done, total = int(fm.group(1)), int(fm.group(2))
    if done is None:
        dm = _DONE.search(rest)
        if dm:
            done = int(dm.group(1))
            tm = _TOTAL.search(rest)
            if tm:
                total = int(tm.group(1))
    return {"ts": ts, "done": done, "total": total, "counters": counters, "fields": fields, "perf": parse_perf_fields(rest)}


def read_tail(path, nbytes):
    with open(path, "rb") as f:
        size = f.seek(0, 2)
        f.seek(max(0, size - nbytes))
        data = f.read()
    text = data.decode("utf-8", "replace")
    lines = text.split("\n")
    if size > nbytes:
        lines = lines[1:]
    return lines


def read_total_file(rundir):
    for n in ("total.txt", "TOTAL"):
        p = os.path.join(rundir, n)
        try:
            with open(p, "r") as f:
                m = re.search(r"\d+", f.read(200))
            if m:
                return int(m.group(0)), n
        except OSError:
            continue
    return None, None


def fmt_left(lo, hi):
    """Remaining-time range in a few characters: '~2-4h', '~40m-2h', '~3h'. lo rounds down, hi up (30 min above 1.5 h, else 5 min)."""
    def part(sec, up):
        if sec >= 5400:
            v = sec / 3600.0
            return (math.ceil(v * 2) if up else math.floor(v * 2)) / 2.0, "h"
        v = sec / 60.0
        return max((math.ceil(v / 5) if up else math.floor(v / 5)) * 5, 5), "m"
    (a, ua), (b, ub) = part(lo, False), part(hi, True)
    if (a, ua) == (b, ub):
        return "~%g%s" % (a, ua)
    return "~%g-%g%s" % (a, b, ub) if ua == ub else "~%g%s-%g%s" % (a, ua, b, ub)


def summarize_progress(samples, rundir, cfg, declared=None, uniform=True):
    """samples: parsed heartbeat samples in file order. Returns progress dict. The total is only ever one the run declared
    (WATCH.json 'total', else a total in the heartbeat line, else total.txt); it is never guessed from file sizes or counts.
    Estimate (only with a total): remaining work over the observed rate, as a RANGE between the recent-window rate and the
    average rate since the run (or its last restart) began, widened by w = 1 + (1 - fraction complete), so an early
    estimate is wide and a late one narrow. It assumes every row costs the same; a run whose rows differ in cost declares
    uniform=False (WATCH.json "uniform_cost": false) and then NO estimate is computed at all: fraction and rate only. Labelled 'rough' while fewer than 5 samples or under 15 min have been observed."""
    prog = {"done": None, "total": None, "percent": None, "rate_per_min": None, "window_s": None,
            "eta_utc": None, "note": None, "counters": None, "fields": None, "total_source": None,
            "eta_lo_utc": None, "eta_hi_utc": None, "left_s": None, "eta_quality": None, "uniform_cost": uniform}
    withdone = [s for s in samples if s["done"] is not None]
    if not withdone:
        prog["note"] = "heartbeat has no progress count"
        return prog
    last = withdone[-1]
    prog["done"] = last["done"]
    prog["counters"] = dict(list(last["counters"].items())[:6]) or None
    prog["fields"] = dict(list(last["fields"].items())[:6]) or None
    if declared:
        total, src = declared, WATCH_FILE
    elif last["total"] is not None:
        total, src = last["total"], "heartbeat"
    else:
        total, src = read_total_file(rundir)
    prog["total"], prog["total_source"] = total, src
    if total:
        prog["percent"] = round(100.0 * min(last["done"], total) / total, 1)
    else:
        prog["note"] = "total unknown"
    # throughput: samples inside the window, after the last decrease of the counter (restart)
    start = 0
    for i in range(1, len(withdone)):
        if withdone[i]["done"] < withdone[i - 1]["done"]:
            start = i
    since_restart = withdone[start:]
    seg = [s for s in since_restart if s["ts"] >= last["ts"] - cfg.window_seconds]
    rates = []
    if len(seg) >= 2 and seg[-1]["ts"] > seg[0]["ts"]:
        dt = seg[-1]["ts"] - seg[0]["ts"]
        rate = (seg[-1]["done"] - seg[0]["done"]) / dt
        prog["window_s"] = int(dt)
        prog["rate_per_min"] = round(rate * 60, 2)
        if rate > 0:
            rates.append(rate)
        else:
            prog["note"] = (prog["note"] + "; " if prog["note"] else "") + "no progress in window"
    else:
        prog["note"] = (prog["note"] + "; " if prog["note"] else "") + "too few heartbeats for a rate"
    span = since_restart[-1]["ts"] - since_restart[0]["ts"]
    if span > 0 and since_restart[-1]["done"] > since_restart[0]["done"]:
        rates.append((since_restart[-1]["done"] - since_restart[0]["done"]) / span)
    if total and not uniform:
        prog["eta_quality"] = "suppressed"     # declared non-uniform cost per row: nothing below is computed, so no width can leak
    elif total and rates and last["done"] < total:
        rem = total - last["done"]
        w = 1.0 + (1.0 - min(last["done"], total) / float(total))
        lo_s, hi_s = rem / max(rates) / w, rem / min(rates) * w
        prog["left_s"] = [int(lo_s), int(hi_s)]
        prog["eta_lo_utc"], prog["eta_hi_utc"] = iso(last["ts"] + lo_s), iso(last["ts"] + hi_s)
        prog["eta_utc"] = iso(last["ts"] + rem / (sum(rates) / len(rates)))
        prog["eta_quality"] = "rough" if (len(since_restart) < 5 or span < 900) else "range"
    return prog


# ----------------------------------------------------------------------------- throughput (CLAUDE.md section 9)
PERF_SKIP = {"ckpt", "merged", "adapter", "checkpoints", "readouts", "kernel_meta", "__pycache__", "trace"}
PERF_MAX_DIRS = 16
PERF_ESCALATION = "decide"       # a throughput regression is treated like a stall
_PROGLOG = re.compile(r"\bstep_s\s+(%s)\s+tok/s/chip\s+(%s)\s+q/s/chip\s+(%s)\s+chips\s+(\d+)\s+reserved_gib\s+(%s)" % ((_NUM,) * 4))


def _fin(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def _perf_rec(source, ts, **kw):
    r = {"source": source, "ts": ts, "utc": iso(ts), "scope": None, "tok_s": None, "ex_s": None, "ex_unit": None, "window": None,
         "chips": None, "procs_on_chip": None, "reserved_gib": None, "step_s": None, "chip_id": None, "baseline": None, "ratio": None,
         "note": None}
    r.update(kw)
    return r


def read_perf_json(path):
    """perf.json -> record or None. Two writers: the trainer (window.*_chip_equiv per-process rates x procs_on_chip, an optional frozen
    'baseline' = the run's own aggregate over steps 20-120, in per-process units) and the eval harness (examples/tokens per second per chip,
    or '_total_for_reference' host rates when chips=0). The ratio is computed here from the raw window and baseline, not copied."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            o = json.load(f)
        mt = os.path.getmtime(path)
    except (OSError, ValueError):
        return None
    if not isinstance(o, dict):
        return None
    um = TS_RE.search(o["utc"]) if isinstance(o.get("utc"), str) else None
    ts = (parse_ts(um) if um else None) or mt
    chips = o.get("chips") if isinstance(o.get("chips"), int) and not isinstance(o.get("chips"), bool) else None
    if isinstance(o.get("window"), dict):
        w = o["window"]
        k = o.get("procs_on_chip") if isinstance(o.get("procs_on_chip"), int) and o["procs_on_chip"] > 0 else 1
        rec = _perf_rec("perf.json", ts, scope="host" if chips == 0 else "chip", ex_unit="q", chips=chips, procs_on_chip=k,
                        window=o.get("window_steps"), step_s=w.get("step_s_mean") if _fin(w.get("step_s_mean")) else None,
                        tok_s=w.get("tok_s_chip_equiv") if _fin(w.get("tok_s_chip_equiv")) else None,
                        ex_s=w.get("q_s_chip_equiv") if _fin(w.get("q_s_chip_equiv")) else None,
                        reserved_gib=o.get("reserved_gib_peak") if _fin(o.get("reserved_gib_peak")) else None)
        b = o.get("baseline")
        if isinstance(b, dict):
            rec["baseline"] = {"steps": b.get("steps"), "n_steps": b.get("n_steps"),
                               "tok_s_proc": b.get("tok_s_proc") if _fin(b.get("tok_s_proc")) else None,
                               "q_s_proc": b.get("q_s_proc") if _fin(b.get("q_s_proc")) else None}
            ratio = {}
            for key, wk in (("tok_s", "tok_s_proc"), ("q_s", "q_s_proc")):
                bv, wv = rec["baseline"].get(wk), w.get(wk)
                if bv and bv > 0 and _fin(wv):
                    ratio[key] = wv / bv
            rec["ratio"] = ratio or None
        return rec
    if "tokens_per_s_per_chip" in o or "examples_per_s_per_chip" in o:
        if chips and chips > 0:
            return _perf_rec("perf.json", ts, scope="chip", ex_unit="ex", chips=chips, tok_s=o.get("tokens_per_s_per_chip"),
                             ex_s=o.get("examples_per_s_per_chip"), window=o.get("window_calls"))
        return _perf_rec("perf.json", ts, scope="host", ex_unit="ex", chips=0 if chips == 0 else None,
                         tok_s=o.get("tokens_per_s_total_for_reference"), ex_s=o.get("examples_per_s_total_for_reference"),
                         window=o.get("window_calls"))
    return None


def read_progress_log_perf(path, window=20):
    """The trainer's progress.log ('step_s 5.12 tok/s/chip 594 q/s/chip 1.95 chips 1 reserved_gib 6.6' per step): median of the last
    `window` step lines, the same statistic as the early baseline. Per-step lines are noisy; the median keeps one slow step out."""
    try:
        lines = read_tail(path, 64 << 10)
    except OSError:
        return None
    recs = []
    for ln in lines:
        m = _PROGLOG.search(ln)
        t = TS_RE.search(ln)
        if m and t and parse_ts(t):
            recs.append((parse_ts(t),) + tuple(float(x) for x in m.groups()))
    recs = recs[-window:]
    if not recs:
        return None
    return _perf_rec("progress.log", recs[-1][0], scope="chip", ex_unit="q", window=len(recs), chips=int(recs[-1][4]),
                     step_s=_median([r[1] for r in recs]), tok_s=_median([r[2] for r in recs]), ex_s=_median([r[3] for r in recs]),
                     reserved_gib=max(r[5] for r in recs), note="median of the last %d step lines" % len(recs))


def _heartbeat_probe(path):
    """ONE read of a (child) heartbeat.log -> (last timestamp of any timestamped line, perf record of the last line that carries
    throughput fields). Both the liveness judgement (stalled or not) and the throughput figure are derived from this single read, so
    they cannot disagree about which lines exist or when they were written. (None, None) when unreadable or empty; a file without a
    single timestamped line reports its mtime as the timestamp and no perf record."""
    try:
        lines = read_tail(path, 64 << 10)
    except OSError:
        return None, None
    last_ts, rec = None, None
    for ln in reversed(lines):
        s = parse_heartbeat_line(ln)
        if not s:
            continue
        if last_ts is None:
            last_ts = s["ts"]
        if s["perf"]:
            rec = _perf_rec("heartbeat", s["ts"], **s["perf"])
            break
    if last_ts is None:
        try:
            last_ts = os.path.getmtime(path)
        except OSError:
            pass
    return last_ts, rec


def _child_dirs(d, cap=300):
    out = []
    try:
        with os.scandir(d) as it:
            for i, e in enumerate(it):
                if i >= cap:
                    break
                if e.is_dir(follow_symlinks=False) and not e.name.startswith(".") and e.name not in PERF_SKIP:
                    out.append(e.path)
    except OSError:
        pass
    return sorted(out)


def perf_dirs(d, depth):
    """The run directory and its descendants down to `depth` levels that hold any throughput source, at most PERF_MAX_DIRS.
    Directory listing is bounded and checkpoint-like directories are skipped, so a huge output tree is never walked."""
    found, level = [], [d]
    for lv in range(depth + 1):
        nxt = []
        for x in level:
            if any(os.path.isfile(os.path.join(x, n)) for n in ("heartbeat.log", "perf.json", "progress.log")):
                found.append(x)
            if lv < depth:
                nxt.extend(_child_dirs(x))
        level = nxt
        if len(found) >= PERF_MAX_DIRS:
            break
    return found[:PERF_MAX_DIRS]


def scan_sources(d, cfg, samples):
    """Every throughput/heartbeat source of one run, read ONCE: the run directory and its descendants down to --throughput-depth
    levels (e.g. workers/w0..w4). Returns (recs, beats): recs = one throughput record per directory that carries any (the freshest of
    heartbeat fields, perf.json and progress.log); beats = (relative dir, timestamp, source) for every directory whose heartbeat or
    progress source was written, including a heartbeat that has no throughput fields (an 'alive' line). The liveness judgement
    (run_liveness) and the throughput aggregate (collect_perf) both consume this one result."""
    recs, beats = [], []
    for x in perf_dirs(d, cfg.perf_depth):
        rel = os.path.relpath(x, d) if x != d else "."
        cands = []
        if x == d:
            own = next((s for s in reversed(samples or []) if s.get("perf")), None)
            if own:
                cands.append(_perf_rec("heartbeat", own["ts"], **own["perf"]))
        else:
            hb = os.path.join(x, cfg.heartbeat_name)
            if os.path.isfile(hb):
                hb_ts, r = _heartbeat_probe(hb)
                if hb_ts is not None:
                    beats.append((rel, hb_ts, cfg.heartbeat_name))
                if r:
                    cands.append(r)
        pj = read_perf_json(os.path.join(x, "perf.json")) if os.path.isfile(os.path.join(x, "perf.json")) else None
        if pj:
            cands.append(pj)
        pl = read_progress_log_perf(os.path.join(x, "progress.log")) if not cands and os.path.isfile(os.path.join(x, "progress.log")) else None
        if pl:
            cands.append(pl)
        if not cands:
            continue
        best = dict(max(cands, key=lambda c: (c["ts"], c["source"] == "heartbeat")))
        if best["source"] != "heartbeat":
            beats.append((rel, best["ts"], best["source"]))
        if pj:
            best["baseline"], best["ratio"], best["perf_json_ts"] = pj["baseline"], pj["ratio"], pj["ts"]
        best["dir"] = rel
        if best["scope"] == "chip" and best["chips"] == 0:
            best["note"] = "chips=0 but per-chip fields present: contradictory source"
        recs.append(best)
    return recs, beats


def run_liveness(d, cfg, own_ts, own_src, srcs):
    """(timestamp, source text) of the newest sign of life of a run across ALL its sources: its own heartbeat and every per-worker
    source in `srcs` (from scan_sources). A run whose root has no heartbeat file but whose workers beat every few seconds is alive."""
    best_ts, best_src = own_ts, own_src
    for rel, ts, src in srcs[1]:
        if best_ts is None or ts > best_ts:
            best_ts, best_src = ts, "newest of %d sub-sources (%s/%s)" % (len(srcs[1]), rel, src)
    return best_ts, best_src


def collect_perf(d, cfg, samples, now, stall_s, srcs=None):
    """Throughput of one run, or None when no source carries any. Sources per directory (the run's own and its children, e.g.
    res/p0..p3 of a concurrent cell, workers/w0..w4): the freshest of heartbeat fields, perf.json and progress.log is the displayed
    rate; the baseline and ratio come only from a perf.json that declares one. Nothing is invented: no baseline declared means ratio
    None. `srcs` is the scan_sources result when the caller already has it (the liveness judgement uses the same one).
    Chip count: where a source names its chip (a worker heartbeat's `chip=N`), chips = the number of DISTINCT chip ids among the live
    sources, one record per chip (the newest), and sources that name no chip are not counted (they are shared streams or aggregates
    of the same workers and would count a chip twice; the note says how many were left out). Where no source names a chip: the sum of
    chips/procs_on_chip as before. Aggregate over the live processes: rate = mean of the per-chip rates, ratio = the worst process."""
    recs = (srcs or scan_sources(d, cfg, samples))[0]
    if not recs:
        return None
    newest = max(r["ts"] for r in recs)
    live = [r for r in recs if newest - r["ts"] <= max(stall_s, 600)]
    unattributed = 0
    if any(r["chip_id"] is not None for r in live):
        by_chip = {}
        for r in live:
            if r["chip_id"] is not None and (r["chip_id"] not in by_chip or r["ts"] > by_chip[r["chip_id"]]["ts"]):
                by_chip[r["chip_id"]] = r
        unattributed = len(live) - sum(1 for r in live if r["chip_id"] is not None)
        live = [by_chip[k] for k in sorted(by_chip)]
    scopes = {r["scope"] for r in live}
    scope = scopes.pop() if len(scopes) == 1 else "mixed"

    def mean(key):
        xs = [r[key] for r in live if _fin(r[key])]
        return sum(xs) / len(xs) if xs else None
    chips = None
    if scope == "host":
        chips = 0
    elif any(r["chip_id"] is not None for r in live):
        chips = len({r["chip_id"] for r in live})
    elif all(r["chips"] is not None for r in live):
        chips = int(math.ceil(sum(r["chips"] / float(max(1, r["procs_on_chip"] or 1)) for r in live) - 1e-9))
    units = {r["ex_unit"] for r in live if r["ex_unit"]}
    rv = [r["reserved_gib"] for r in live if _fin(r["reserved_gib"])]
    pk = [r["procs_on_chip"] for r in live if r["procs_on_chip"]]
    key = cfg.perf_ratio_key
    ratios = []
    for r in live:
        if r["ratio"] and key in r["ratio"] and r.get("perf_json_ts") is not None:
            ratios.append((r["ratio"][key], r["dir"], now - r["perf_json_ts"] <= max(stall_s, 600)))
    worst = min(ratios) if ratios else None
    return {
        "scope": scope, "tok_s": mean("tok_s"), "ex_s": mean("ex_s"), "ex_unit": units.pop() if len(units) == 1 else "ex",
        "window": next((r["window"] for r in live if r["window"]), None), "chips": chips, "n_procs": len(live),
        "procs_on_chip": max(pk) if pk else None, "reserved_gib": max(rv) if rv else None, "utc": iso(newest), "age_s": int(now - newest),
        "sources": sorted({r["source"] for r in live}),
        "baseline": "declared" if worst else "undeclared", "ratio_key": key, "ratio": worst[0] if worst else None,
        "ratio_dir": worst[1] if worst else None, "ratio_stale": bool(worst and not worst[2]),
        "threshold": cfg.perf_regress_ratio, "regressed": bool(worst and worst[2] and worst[0] < cfg.perf_regress_ratio),
        "note": ("; ".join(sorted({r["note"] for r in live if r["note"]} | (
            {"%d source(s) naming no chip not counted" % unattributed} if unattributed else set()))) or None),
        "chip_ids": sorted({r["chip_id"] for r in live if r["chip_id"] is not None}) or None,
        "procs": [{k: r[k] for k in ("dir", "source", "utc", "scope", "tok_s", "ex_s", "ex_unit", "window", "chips", "procs_on_chip",
                                      "reserved_gib", "baseline", "ratio")} for r in live][:PERF_MAX_DIRS],
    }


def _perf_cell(p):
    """Row text. Per-chip rates say per chip, the chip count (xN; /Kp = K processes share a chip) and the reserved GiB per process;
    host rates of a chip-less run say host and are never labelled per chip. r= ratio to the declared baseline, base? = none declared."""
    if not p:
        return "-"
    parts = []
    if p["scope"] == "host":
        if p["tok_s"] is not None:
            parts.append("%.0f tok/s" % p["tok_s"])
        if p["ex_s"] is not None:
            parts.append("%.2f %s/s" % (p["ex_s"], p["ex_unit"] or "ex"))
        return "host " + ", ".join(parts) + " (chips=0)" + (" base?" if p["baseline"] == "undeclared" else "")
    if p["tok_s"] is not None:
        parts.append("%.0f tok/s/chip" % p["tok_s"])
    if p["ex_s"] is not None:
        parts.append("%.2f %s/s/chip" % (p["ex_s"], p["ex_unit"] or "ex"))
    if p["chips"] is not None:
        parts.append("x%d%s" % (p["chips"], "/%dp" % p["procs_on_chip"] if (p["procs_on_chip"] or 1) > 1 else ""))
    if p["reserved_gib"] is not None:
        parts.append("%.1fGiB" % p["reserved_gib"])
    parts.append(("r=%.2f%s" % (p["ratio"], "(stale)" if p["ratio_stale"] else "")) if p["ratio"] is not None else "base?")
    return " ".join(parts)


# ----------------------------------------------------------------------------- suspicious metrics
def _fmt_key(k):
    return ".%s" % k if re.match(r"^[A-Za-z_]\w*$", k) else "[%s]" % json.dumps(k)


def jpath(parts):
    return "$" + "".join("[%d]" % p if isinstance(p, int) else _fmt_key(p) for p in parts)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _children(node):
    if isinstance(node, dict):
        return list(node.items())
    if isinstance(node, list):
        return list(enumerate(node))
    return None


def _flatten(node, prefix, depth, out):
    ch = _children(node)
    if ch is None:
        out[prefix] = node
        return
    if depth == 0:
        return
    for k, v in ch:
        _flatten(v, prefix + (k,), depth - 1, out)


def _rate_ctx(parts, cfg, leaf_only=False):
    strs = [p for p in parts if isinstance(p, str)]
    if not strs:
        return False
    cands = strs[-1:] if leaf_only else strs[-3:]
    return any(cfg.rate_re.search(c) for c in cands)


def _is_count_key(parts, cfg):
    return bool(parts) and isinstance(parts[-1], str) and bool(cfg.count_re.match(parts[-1]))


def _suppressed_by(parts, cfg, primary_name=None):
    """Role that makes a value expected-degenerate, or None. Protected roles always win, except that the
    'primary' role of a report whose primary scorer is itself a mock (mock-*) is a mock, so it is suppressed
    as that mock. decision_lines belong to the primary scorer."""
    segs = [p for p in parts if isinstance(p, str)]
    if segs and segs[0] == "decision_lines":
        segs = segs + ["primary"]
    if not cfg.suppress_pats:
        return None
    mock_primary = None
    if primary_name and "primary" in segs and any(fnmatch.fnmatchcase(primary_name, p) for p in cfg.suppress_pats):
        mock_primary = "primary=" + primary_name
        segs = [sg for sg in segs if sg != "primary"]
    if any(sg in cfg.protect_set for sg in segs):
        return None
    for sg in segs:
        for pat in cfg.suppress_pats:
            if fnmatch.fnmatchcase(sg, pat):
                return sg
    return mock_primary


def check_report(obj, cfg):
    items = _check_report(obj, cfg)
    pn = obj.get("primary") if isinstance(obj, dict) and isinstance(obj.get("primary"), str) else None
    for it in items:
        it["suppressed_by"] = None
        segs = [p for p in it["_parts"] if isinstance(p, str)]
        it["scope"] = "primary" if ("primary" in segs or (segs and segs[0] == "decision_lines")) else "other"
        if it["kind"] in ("exact_zero", "exact_one", "identical_across_cells"):
            it["suppressed_by"] = _suppressed_by(it.pop("_parts"), cfg, pn)
        else:
            it.pop("_parts", None)
    return items


def _check_report(obj, cfg):
    """Pure detector. Returns a list of {kind, path, value, detail}. Kinds: exact_zero, exact_one,
    identical_across_cells, low_sample_count, non_finite."""
    items = []
    leaves = {}
    _flatten(obj, (), 64, leaves)
    # 1. exact 0.0 / 1.0 on rate-like numbers, and non-finite numbers anywhere
    for parts, v in leaves.items():
        if not _is_num(v):
            continue
        if isinstance(v, float) and not math.isfinite(v):
            items.append({"kind": "non_finite", "path": jpath(parts), "value": str(v), "detail": "NaN or infinite value", "_parts": parts})
            continue
        if _is_count_key(parts, cfg) or v not in (0, 1):
            continue
        if isinstance(v, int) and not _rate_ctx(parts, cfg, leaf_only=True):
            continue
        if _rate_ctx(parts, cfg):
            items.append({"kind": "exact_zero" if v == 0 else "exact_one", "path": jpath(parts), "value": v,
                          "detail": "rate/accuracy exactly %s" % ("0.0" if v == 0 else "1.0"), "_parts": parts})
    # 2. identical metric across every cell of a table (post-order so deeper tables claim their leaves first)
    covered = set()

    def visit(node, parts):
        ch = _children(node)
        if ch is None:
            return
        for k, v in ch:
            visit(v, parts + (k,))
        if len(ch) < cfg.min_cells:
            return
        vals = [v for _, v in ch]
        if all(_is_num(v) for v in vals):
            if _rate_ctx(parts, cfg) and not _is_count_key(parts, cfg) and \
                    all(math.isfinite(float(v)) for v in vals) and len(set(float(v) for v in vals)) == 1:
                leafp = {parts + (k,) for k, _ in ch}
                if not leafp <= covered:
                    covered.update(leafp)
                    items.append({"kind": "identical_across_cells", "path": jpath(parts), "value": vals[0],
                                  "detail": "all %d cells equal; input may never have varied" % len(ch), "_parts": parts})
            return
        if not all(isinstance(v, (dict, list)) for v in vals):
            return
        flats = []
        for _, v in ch:
            d = {}
            _flatten(v, (), 4, d)
            flats.append(d)
        common = set(flats[0])
        for d in flats[1:]:
            common &= set(d)
        for rel in sorted(common, key=lambda r: [str(x) for x in r]):
            fv = [d[rel] for d in flats]
            if not all(_is_num(v) for v in fv):
                continue
            absp = parts + (ch[0][0],) + rel
            if _is_count_key(rel, cfg) or not _rate_ctx(parts + rel, cfg):
                continue
            if not all(math.isfinite(float(v)) for v in fv) or len(set(float(v) for v in fv)) != 1:
                continue
            leafp = {parts + (k,) + rel for k, _ in ch}
            if leafp <= covered:
                continue
            covered.update(leafp)
            items.append({"kind": "identical_across_cells", "path": jpath(parts) + "[*]" + jpath(rel)[1:],
                          "value": fv[0], "detail": "same value in all %d cells; input may never have varied" % len(ch),
                          "_parts": parts + rel})

    visit(obj, ())
    # 3. cells with a small sample count
    def visit_n(node, parts):
        ch = _children(node)
        if ch is None:
            return
        for k, v in ch:
            visit_n(v, parts + (k,))
        if isinstance(node, dict) and len(node) >= 2:
            for k, v in node.items():
                if isinstance(k, str) and cfg.count_re.match(k) and _is_num(v) and v < cfg.min_n:
                    items.append({"kind": "low_sample_count", "path": jpath(parts + (k,)), "value": v,
                                  "detail": "n=%s below minimum %d" % (v, cfg.min_n), "_parts": parts})

    visit_n(obj, ())
    return items


def scan_report(path, cfg):
    """Returns (items, error_note)."""
    try:
        if os.path.getsize(path) > 100 << 20:
            return [], "report.json larger than 100 MB, not scanned"
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, ValueError) as e:
        return [], "report.json unreadable: %s" % str(e)[:80]
    return check_report(obj, cfg), None


def group_flags(all_items, cfg):
    items = [i for i in all_items if not i["suppressed_by"]]
    supp = {}
    for i in all_items:
        if i["suppressed_by"]:
            supp[i["suppressed_by"]] = supp.get(i["suppressed_by"], 0) + 1
    by = {}
    for it in items:
        by.setdefault((it["scope"], it["kind"]), []).append(it)
    out = {"total": len(items), "by_kind": {}, "by_scope": {"primary": {}, "other": {}}, "items": [], "omitted": 0,
           "suppressed": {"total": sum(supp.values()), "by_role": dict(sorted(supp.items()))}}
    for (scope, kind) in sorted(by):
        lst = by[(scope, kind)]
        out["by_kind"][kind] = out["by_kind"].get(kind, 0) + len(lst)
        out["by_scope"][scope][kind] = len(lst)
        out["items"].extend(lst[:cfg.max_flags_per_kind])
        out["omitted"] += max(0, len(lst) - cfg.max_flags_per_kind)
    return out


# ----------------------------------------------------------------------------- discovery & classification
def _entries(d):
    try:
        with os.scandir(d) as it:
            return [(e.name, e.is_dir(follow_symlinks=False)) for e in it]
    except OSError:
        return []


def run_logs(d, cfg):
    files = []
    for pat in cfg.globs:
        files.extend(glob.glob(os.path.join(glob.escape(d), pat)))
    parent, name = os.path.split(d.rstrip("/"))
    files.extend(glob.glob(os.path.join(glob.escape(parent), glob.escape(name) + ".*log")))
    hb = os.path.join(d, cfg.heartbeat_name)
    out = sorted({f for f in files if os.path.isfile(f) and f != hb})
    return out


def is_run_dir(d, entries, depth, cfg):
    names = {n for n, isdir in entries if not isdir}
    strong = bool(names & set(cfg.markers)) or cfg.heartbeat_name in names
    if depth == 0:
        return strong
    if strong or cfg.report_name in names:
        return True
    if any(fnmatch.fnmatch(n, g) for n in names for g in cfg.globs if "/" not in g):
        return True
    return bool(run_logs(d, cfg))


def discover(cfg, queued=None):
    """Runs below the roots. `queued`, when a list, receives the ids of directories that hold a queued-file (--queued-names) but no
    terminal marker and no heartbeat file: work that has been queued and has not started."""
    runs, seen = [], set()
    roots = [os.path.abspath(r) for r in cfg.root]
    for root in roots:
        def walk(d, depth):
            real = os.path.realpath(d)
            if real in seen or real == cfg.out_dir:
                return
            ents = _entries(d)
            rid = os.path.relpath(d, root) if d != root else os.path.basename(root)
            if len(roots) > 1:
                rid = os.path.basename(root) + ":" + rid
            if queued is not None and cfg.queued_files:
                fn = {n for n, isdir in ents if not isdir}
                if fn & set(cfg.queued_files) and not fn & set(cfg.markers) and cfg.heartbeat_name not in fn:
                    queued.append(rid)
            if is_run_dir(d, ents, depth, cfg):
                seen.add(real)
                runs.append({"id": rid, "path": d, "root": root, "id_prefix": os.path.basename(root) + ":" if len(roots) > 1 else ""})
                return
            if depth >= cfg.max_depth:
                return
            for n, isdir in sorted(ents):
                if isdir and not n.startswith((".", "_")) and n not in cfg.skip:
                    walk(os.path.join(d, n), depth + 1)
        if os.path.isdir(root):
            walk(root, 0)
    return runs


MARKER_JSON_KEYS = ("exit_code", "exit_status", "returncode", "return_code", "rc")
MARKER_UNPARSEABLE = "MARKER UNPARSEABLE"
MARKER_CONFLICT = "MARKER CONFLICT"


def parse_marker_content(content):
    """-> (exit_code or None, utc text or None, problem or None). A marker is either plain text (`rc=0 utc=...`, `exit_code: 0` or a
    bare integer) or a JSON object whose exit code is an integer under one of MARKER_JSON_KEYS (first present key wins). A JSON marker
    that holds exit code 0 together with a non-empty `error` is a contradiction, not a success."""
    txt = content.strip()
    if txt.startswith("{"):
        try:
            o = json.loads(txt)
        except ValueError as e:
            return None, None, "JSON marker does not parse (%s)" % str(e)[:60]
        if not isinstance(o, dict):
            return None, None, "JSON marker is not an object"
        key = next((k for k in MARKER_JSON_KEYS if k in o), None)
        if key is None:
            return None, None, "JSON marker has none of the keys %s" % "/".join(MARKER_JSON_KEYS)
        v = o[key]
        if isinstance(v, bool) or not isinstance(v, int):
            return None, None, "JSON marker key %s is %s, not an integer" % (key, type(v).__name__)
        utc = o.get("utc") if isinstance(o.get("utc"), str) else None
        if v == 0 and o.get("error"):
            return v, utc, "JSON marker holds %s 0 and a non-empty error field" % key
        return v, utc, None
    m = re.search(r"(?:\brc|exit(?:[_ ]?code)?)\s*[=:]\s*(-?\d+)", content, re.I)
    if m is None:
        m = re.match(r"\s*(-?\d+)\b", content)
    return (int(m.group(1)) if m else None), None, (None if m else "no integer exit code found")


def read_marker(d, cfg):
    """Returns (marker_dict_or_None, problem_or_None). A problem always starts with a named condition (MARKER UNPARSEABLE or MARKER
    CONFLICT); a run that has a marker file is terminal and is never classified stalled, whatever its heartbeats say."""
    found = []
    for name in cfg.markers:
        p = os.path.join(d, name)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(4000)
            mtime = os.path.getmtime(p)
        except OSError:
            continue
        rc, jutc, prob = parse_marker_content(content)
        um = TS_RE.search(jutc or content)
        ts = parse_ts(um) if um else None
        found.append({"name": name, "path": p, "exit_code": rc, "utc": iso(ts) if ts else iso(mtime),
                      "ts": ts if ts else mtime, "empty": not content.strip(), "problem": prob})
    if not found:
        return None, None
    rcs = {m["exit_code"] for m in found if m["exit_code"] is not None}
    names = ",".join(m["name"] for m in found)
    mk = dict(found[0])
    bad = [m for m in found if m["problem"]]
    if bad:                      # a marker we cannot read is never ignored, even beside one we can
        m = bad[0]
        kind = MARKER_CONFLICT if m["exit_code"] is not None else MARKER_UNPARSEABLE
        return mk, "%s: marker %s: %s" % (kind, m["name"], m["problem"])
    if not rcs:
        return mk, "%s: marker %s present but holds no parseable exit code" % (MARKER_UNPARSEABLE, names)
    if len(rcs) > 1:
        return mk, "%s: markers %s disagree on the exit code (%s)" % (MARKER_CONFLICT, names, sorted(rcs))
    rc = rcs.pop()
    mk["exit_code"] = rc
    if rc == 0 and any(m["name"].upper() == "FAILED" for m in found):
        return mk, "%s: FAILED marker holds exit code 0" % MARKER_CONFLICT
    if rc != 0 and any(m["name"].upper() == "DONE" for m in found):
        return mk, "%s: DONE marker holds non-zero exit code %d" % (MARKER_CONFLICT, rc)
    return mk, None


def classify(marker, problem, hb_ts, hb_src, has_logs, now, cfg, has_hb_file=True, stall=None):
    """Deterministic state from the marker and heartbeat only. Returns (state, reason)."""
    if marker is not None:
        if problem:
            return "unknown", problem
        if marker["exit_code"] == 0:
            return "done", "marker %s exit code 0" % marker["name"]
        return "failed", "marker %s exit code %d" % (marker["name"], marker["exit_code"])
    if hb_ts is None:
        return "unknown", ("log present but no heartbeat or readable mtime" if has_logs
                           else "no log and no terminal marker (output files only)")
    stall = cfg.stall_seconds if stall is None else stall
    age = now - hb_ts
    if age < -cfg.clock_skew_seconds:
        return "unknown", "heartbeat %ds in the future (clock skew between hosts?)" % int(-age)
    if age <= stall:
        return "running", "heartbeat %s ago via %s" % (human_age(age), hb_src)
    if not has_hb_file and age > cfg.archive_seconds:
        return "archived", "no marker or heartbeat file, newest log %s old (> %s archive threshold)" % (
            human_age(age), human_age(cfg.archive_seconds))
    return "stalled", "heartbeat %s old (> %ds) via %s, no marker" % (human_age(age), int(stall), hb_src)


def read_watch_file(d):
    """(tier or None, declared total or None, uniform_cost, error or None) from WATCH.json.
    tier: only the exact strings fast|medium|slow. total: a positive JSON integer, the run's own count of rows it intends to
    write (in the unit of the progress count: the sum of the heartbeat row counters). uniform_cost: optional JSON boolean, default true;
    false says the run's rows differ in cost, so the remaining-time estimate is suppressed. Anything else is an error naming the file."""
    p = os.path.join(d, WATCH_FILE)
    if not os.path.isfile(p):
        return None, None, True, None
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, ValueError) as e:
        return None, None, True, "%s unreadable or not JSON: %s" % (p, str(e)[:60])
    if not isinstance(obj, dict):
        return None, None, True, "%s must hold a JSON object" % p
    tier = total = None
    if "tier" in obj:
        tier = obj["tier"]
        if not isinstance(tier, str) or tier not in TIER_NAMES:
            return None, None, True, "%s: invalid tier %s (expected exactly one of %s)" % (p, json.dumps(tier)[:40], "|".join(TIER_NAMES))
    if "total" in obj:
        total = obj["total"]
        if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
            return None, None, True, "%s: invalid total %s (expected a positive JSON integer)" % (p, json.dumps(total)[:40])
    uniform = True
    if "uniform_cost" in obj:
        uniform = obj["uniform_cost"]
        if not isinstance(uniform, bool):
            return None, None, True, "%s: invalid uniform_cost %s (expected true or false)" % (p, json.dumps(uniform)[:40])
    return tier, total, uniform, None


def infer_period(samples):
    """(period_s, n_gaps, how) from the most recent heartbeat timestamps; period None when there is no positive gap.
    Timestamps are sorted and deduplicated, so a bursty or out-of-order file cannot produce zero or negative gaps.
    With fewer than INFER_MEDIAN_GAPS gaps the MAX gap is used, with more the median. Thin evidence errs long: a false
    stall costs an escalation, a late stall detection costs almost nothing."""
    ts = sorted({x["ts"] for x in samples})[-INFER_WINDOW:]
    gaps = sorted(b - a for a, b in zip(ts, ts[1:]))
    n = len(gaps)
    if n < INFER_MIN_GAPS:
        return None, n, None
    if n < INFER_MEDIAN_GAPS:
        return gaps[-1], n, "max"
    return (gaps[n // 2] if n % 2 else (gaps[n // 2 - 1] + gaps[n // 2]) / 2.0), n, "median"


def resolve_tier(d, samples, cfg):
    """Tier for one run. Precedence: WATCH.json, then the run's own heartbeat period, then medium.
    Returns {name, source, recheck_s, stall_s, error}; cfg.stall_seconds, when set, overrides every stall threshold."""
    tier, declared, uniform, err = read_watch_file(d)
    if err:
        t = dict(cfg.tiers["medium"], name="medium", source="default (WATCH.json invalid)", short="dflt", error=err)
    elif tier:
        t = dict(cfg.tiers[tier], name=tier, source="WATCH.json", short="file", error=None)
    else:
        per, ngaps, how = infer_period(samples)
        if per is not None:
            lo, hi = cfg.tiers["fast"]["recheck_s"], cfg.tiers["slow"]["recheck_s"]
            t = {"name": "auto", "source": "heartbeat period %s (%s of %d gap%s)" % (human_age(per), how, ngaps, "" if ngaps == 1 else "s"),
                 "short": "hb" + human_age(per), "recheck_s": min(max(per, lo), hi),
                 "stall_s": max(cfg.stall_floor, cfg.stall_multiple * per), "error": None}
        else:
            t = dict(cfg.tiers["medium"], name="medium", short="dflt", error=None,
                     source="default (no heartbeat gap to infer from)")
    if cfg.stall_seconds is not None:
        t["stall_s"] = cfg.stall_seconds
        t["source"] += "; stall from --stall-seconds"
    t["declared_total"], t["uniform_cost"] = declared, uniform
    return t


def escalate(state, flags_total, sigs):
    if state == "archived":
        return "none", ""
    has_err = any(s["severity"] == "error" for s in sigs)
    if state == "failed":
        return "decide", "run failed"
    if state == "stalled":
        return "decide", "run stalled without a marker"
    if state == "done" and flags_total:
        return "decide", "finished, but %d suspicious metric(s): accept or reject the result" % flags_total
    if state == "unknown":
        return "read", "state unknown; a reader must look"
    if flags_total:
        return "read", "%d suspicious metric(s) in a partial report" % flags_total
    if has_err:
        return "read", "error lines in log"
    return "none", ""


def exemplar_range(sig, last_line):
    if re.search(r"traceback", sig["_text"], re.I):
        s, e = sig["_line"], sig["_line"] + sig["_cb"] + sig["_ca"]
    else:
        s, e = max(1, sig["_line"] - sig["_cb"]), sig["_line"] + sig["_ca"]
    return s, max(s, min(e, last_line)) if last_line else e


def read_why(d, cfg):
    """One short line from WHY_STOPPED.json / WHY_FAILED.json, so an explained failure is not re-diagnosed."""
    for name in cfg.why_files:
        p = os.path.join(d, name)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read(65536)
        except OSError:
            continue
        note = None
        expected = subtree = False
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                expected = obj.get("expected") is True   # strictly the boolean true; never inferred from prose
                subtree = obj.get("applies_to_subtree") is True
                for k in ("subtree_note", "note", "why", "reason", "summary", "cause", "message"):
                    if isinstance(obj.get(k), str):
                        note = obj[k]
                        break
                if note is None:
                    note = next((v for v in obj.values() if isinstance(v, str)), None)
            elif isinstance(obj, str):
                note = obj
        except ValueError:
            pass
        if note is None:
            note = raw
        return {"file": name, "note": " ".join(note.split())[:300], "expected": expected, "applies_to_subtree": subtree}
    return None


def inherited_why(run, cfg):
    """Disposition inherited from a directory above the run, or None. Walk up from the run's parent to (not including) its root;
    the NEAREST ancestor whose WHY file sets "applies_to_subtree": true decides: with "expected": true the run inherits it; with
    anything else the search stops and nothing is inherited (a nearer explicit refusal is not overridden by a farther file). A WHY
    file without applies_to_subtree: true never reaches below its own directory, and neither does one at a root. Both keys must be the
    JSON boolean true. A run's own WHY file is consulted before this and always wins."""
    root = run.get("root")
    if not root:
        return None
    d = os.path.dirname(run["path"].rstrip("/"))
    root = root.rstrip("/")
    while d.startswith(root + os.sep):
        w = read_why(d, cfg)
        if w and w["applies_to_subtree"]:
            if not w["expected"]:
                return None
            rel = os.path.relpath(d, root)
            return dict(w, inherited_from=run.get("id_prefix", "") + rel, inherited_dir=d)
        d = os.path.dirname(d)
    return None


def read_heartbeat(d, cfg):
    """(samples, hb_ts, hb_src, notes) from the heartbeat file; empty/None when there is none."""
    samples, hb_ts, hb_src, notes = [], None, None, []
    hbp = os.path.join(d, cfg.heartbeat_name)
    if os.path.isfile(hbp):
        try:
            for ln in read_tail(hbp, 256 << 10)[-2000:]:
                s = parse_heartbeat_line(ln)
                if s:
                    samples.append(s)
            if samples:
                hb_ts, hb_src = samples[-1]["ts"], cfg.heartbeat_name
            else:
                hb_ts, hb_src = os.path.getmtime(hbp), cfg.heartbeat_name + " mtime (no timestamped lines)"
        except OSError as e:
            notes.append("heartbeat unreadable: %s" % str(e)[:60])
    return samples, hb_ts, hb_src, notes


def flat_stretch(samples):
    """The trailing run of heartbeat samples with an unchanged progress count, or None when there are fewer than 3 of them
    (one repeated value is just a slow moment). since = when that count was first seen."""
    wd_ = [x for x in samples if x["done"] is not None]
    if len(wd_) < 3:
        return None
    i = len(wd_) - 1
    while i > 0 and wd_[i - 1]["done"] == wd_[-1]["done"]:
        i -= 1
    n = len(wd_) - i
    if n < 3:
        return None
    return {"since": wd_[i]["ts"], "flat_s": wd_[-1]["ts"] - wd_[i]["ts"], "samples": n, "done": wd_[-1]["done"]}


_SHARD_DONE = re.compile(r"\bshard\s+(\d+)\s*/\s*(\d+)\s+done\b", re.I)


def shard_status(d, last_sample):
    """Tell shards that finished from shards that vanished, from the evidence only. The heartbeat gives alive/total; each
    logs/shard*.log of a finished shard ends with 'shard N/M done'. Returns a dict, or None when the heartbeat has no shard
    counts. 'lost' is set only when the number of shard logs equals the total and alive + finished falls short of it;
    otherwise the cause is stated as not determinable. Never guessed."""
    f = (last_sample or {}).get("fields") or {}
    if "alive_shards" not in f or "shards_total" not in f:
        return None
    alive, total = f["alive_shards"], f["shards_total"]
    logs = sorted(glob.glob(os.path.join(d, "logs", "shard*.log")))
    out = {"alive": alive, "total": total, "finished": None, "lost": None, "note": None}
    if len(logs) != total:
        out["note"] = "%d shard logs for %d shards: finished vs lost not determinable" % (len(logs), total)
        return out
    fin = 0
    for lg in logs:
        try:
            if _SHARD_DONE.search("\n".join(read_tail(lg, 4096)[-5:])):
                fin += 1
        except OSError:
            pass
    out["finished"] = fin
    out["lost"] = max(0, total - alive - fin)
    if out["lost"]:
        out["note"] = "%d of %d shards neither alive nor finished (no 'done' line in their logs)" % (out["lost"], total)
    return out


def refresh_cached(res, d, cfg, now):
    """Cheap per-tick refresh of a not-due run: only the heartbeat tails are re-read, so its progress, heartbeat time and age
    track the run. State, errors and report stay as of the last full read. The heartbeat time is computed by live_timestamp, the
    same function as the full read, over the same sources as the throughput figure."""
    samples, hb_ts, hb_src, _ = read_heartbeat(d, cfg)
    srcs = scan_sources(d, cfg, samples)
    if samples:
        res["progress"] = summarize_progress(samples, d, cfg, res.get("declared_total"), res.get("uniform_cost", True))
    ts, src = live_timestamp(d, cfg, run_logs(d, cfg), hb_ts if samples else None, hb_src if samples else None, srcs)
    if ts is not None and (samples or srcs[1]):
        res["heartbeat_epoch"], res["heartbeat_utc"], res["heartbeat_source"] = ts, iso(ts), src
        res["age_s"] = int(now - ts)
    elif res.get("heartbeat_epoch") is not None:
        res["age_s"] = int(now - res["heartbeat_epoch"])
    res["perf"] = collect_perf(d, cfg, samples, now, res["tier"]["stall_s"], srcs)     # rates follow every tick; the regression ESCALATION is set at full reads
    return res


def live_timestamp(d, cfg, logs, hb_ts, hb_src, srcs):
    """The single liveness timestamp of a run, used by the full read (evaluate_run) AND the per-tick refresh (refresh_cached) so the
    two cannot disagree: the newest of the run's own heartbeat (or, when it has none, the mtime of its newest log) and every per-worker
    source of scan_sources, which is the very set the throughput figure is computed from."""
    if hb_ts is None and logs:
        mt = []
        for lg in logs:
            try:
                mt.append((os.path.getmtime(lg), lg))
            except OSError:
                pass
        if mt:
            t, lg = max(mt)
            hb_ts, hb_src = t, "mtime of %s (no heartbeat file)" % os.path.basename(lg)
    return run_liveness(d, cfg, hb_ts, hb_src, srcs)


def evaluate_run(run, cfg, states, now, prev=None):
    """prev: None in a one-shot pass; in --watch the previous result for this run ({} on the first read)."""
    d = run["path"]
    notes = []
    marker, problem = read_marker(d, cfg)
    logs = run_logs(d, cfg)
    hbp = os.path.join(d, cfg.heartbeat_name)
    samples, hb_ts, hb_src, hb_notes = read_heartbeat(d, cfg)
    notes.extend(hb_notes)
    srcs = scan_sources(d, cfg, samples)
    hb_ts, hb_src = live_timestamp(d, cfg, logs, hb_ts, hb_src, srcs)
    tier = resolve_tier(d, samples, cfg)
    state, reason = classify(marker, problem, hb_ts, hb_src, bool(logs), now, cfg, os.path.isfile(hbp), stall=tier["stall_s"])
    if tier["error"]:
        state, reason = "unknown", tier["error"]
    if marker and hb_ts and marker["exit_code"] is not None and hb_ts > marker["ts"] + tier["stall_s"]:
        notes.append("heartbeat newer than marker; marker may be stale")

    # logs -> signatures
    sigs_all, dropped, last_lines, newest = {}, 0, {}, None
    for lg in logs:
        st = states.setdefault(lg, LogState())
        scan_log(lg, st, cfg, now)
        last_lines[lg] = st.lineno
        dropped += st.dropped
        try:
            mt = os.path.getmtime(lg)
            if newest is None or mt > newest[0]:
                newest = (mt, lg)
        except OSError:
            pass
        for sig, e in st.sigs.items():
            cur = sigs_all.get(sig)
            if cur is None:
                cur = sigs_all[sig] = {"signature": sig, "severity": e.sev, "count": 0, "first_ts": None, "last_ts": None,
                                       "log": lg, "line": e.ex_line, "byte": e.ex_byte, "text": e.ex_text,
                                       "last_line": e.last_line, "last_log": lg}
            cur["count"] += e.count
            if e.first_ts is not None and (cur["first_ts"] is None or e.first_ts < cur["first_ts"]):
                cur["first_ts"] = e.first_ts
            if e.last_ts is not None and (cur["last_ts"] is None or e.last_ts > cur["last_ts"]):
                cur["last_ts"] = e.last_ts
    ranked = sorted(sigs_all.values(), key=lambda s: (s["severity"] != "error", -s["count"], s["signature"]))
    shown = ranked[:cfg.max_signatures]
    out_sigs = []
    for s in shown:
        s2 = dict(s, _text=s["text"], _line=s["line"], _cb=cfg.ctx_before, _ca=cfg.ctx_after)
        a, b = exemplar_range(s2, last_lines.get(s["log"]))
        out_sigs.append({
            "signature": s["signature"], "severity": s["severity"], "count": s["count"],
            "first_utc": iso(s["first_ts"]), "last_utc": iso(s["last_ts"]), "last_line": s["last_line"],
            "exemplar": {"log": s["log"], "line_start": a, "line_end": b, "line": s["line"], "byte_offset": s["byte"],
                         "text": redact(" ".join(s["text"].split()))[:cfg.exemplar_width]}})
    omitted = ranked[cfg.max_signatures:]
    n_err = sum(s["count"] for s in sigs_all.values() if s["severity"] == "error")
    n_warn = sum(s["count"] for s in sigs_all.values() if s["severity"] == "warning")
    errors = {"error_lines": n_err, "warning_lines": n_warn, "distinct_signatures": len(sigs_all) + (1 if dropped else 0),
              "signatures": out_sigs, "omitted_signatures": len(omitted),
              "omitted_occurrences": sum(s["count"] for s in omitted), "untracked_lines": dropped}

    # report.json
    rp = os.path.join(d, cfg.report_name)
    sus = {"total": 0, "by_kind": {}, "items": [], "omitted": 0, "report": None, "by_scope": {"primary": {}, "other": {}},
           "suppressed": {"total": 0, "by_role": {}}}
    if os.path.isfile(rp):
        items, err = scan_report(rp, cfg)
        sus = group_flags(items, cfg)
        sus["report"] = rp
        if err:
            notes.append(err)

    esc, why_text = escalate(state, sus["total"], out_sigs)
    condition = None
    if marker is not None and problem and state == "unknown":
        # A marker file exists, so the run is terminal; what is unknown is its outcome. Named, not a generic "unknown".
        condition = "marker_conflict" if problem.startswith(MARKER_CONFLICT) else "marker_unparseable"
        esc, why_text = "read", problem
    progress = summarize_progress(samples, d, cfg, tier.get("declared_total"), tier.get("uniform_cost", True)) if samples else None
    # Declared-total anomalies. Exceeded: the run wrote more rows than it declared, so the declaration or the run is wrong.
    # Unreachable: even the optimistic end of the estimate is past --deadline-hours. Never raised without a declaration.
    anomaly = None
    if progress and progress["total"] and progress["total_source"] == WATCH_FILE and state in ("running", "done"):
        if progress["done"] > progress["total"]:
            anomaly = "TOTAL EXCEEDED: %d rows vs declared %d" % (progress["done"], progress["total"])
        elif state == "running" and progress["left_s"] and progress["eta_quality"] == "range" \
                and progress["left_s"][0] > cfg.deadline_hours * 3600:
            anomaly = "TOTAL UNREACHABLE: even the optimistic estimate needs %s more (> %gh deadline)" % (
                human_age(progress["left_s"][0]), cfg.deadline_hours)
    # Fresh heartbeat, flat progress: the heartbeat thread lives but the work has stopped. Flagged only when the flat stretch is
    # at least --flat-multiple x the run's stall threshold AND (in --watch) it was seen flat by two consecutive full reads.
    flat_info, flat_reads, flat_done = None, 0, None
    st_flat = flat_stretch(samples) if state == "running" else None
    if st_flat and st_flat["flat_s"] >= cfg.flat_multiple * tier["stall_s"]:
        flat_done = st_flat["done"]
        flat_reads = (prev.get("flat_reads", 0) + 1) if prev and prev.get("flat_done") == flat_done else 1
        flat_info = dict(st_flat, since_utc=iso(st_flat["since"]), reads=flat_reads,
                         confirmed=(prev is None or flat_reads >= 2))
        del flat_info["since"]
    flat_on = bool(flat_info and flat_info["confirmed"])
    if flat_on:
        ftxt = "PROGRESS FLAT %s at %d with a fresh heartbeat (wedged shard or hung call?)" % (human_age(flat_info["flat_s"]), flat_done)
        if esc == "none":
            esc, why_text = "read", ftxt
        else:
            why_text = ftxt + "; " + (why_text or "")
    if anomaly:
        if esc == "none":
            esc, why_text = "read", anomaly
        else:
            why_text = anomaly + "; " + (why_text or "")
    # Throughput regression: a RUNNING run that declares an early baseline (perf.json) and whose windowed rate fell below
    # --perf-regress-ratio x that baseline. Treated like a stall (escalates). No declared baseline: nothing is flagged, nothing invented.
    perf = collect_perf(d, cfg, samples, now, tier["stall_s"], srcs)
    perf_on = bool(perf and perf["regressed"] and state == "running")
    if perf_on:
        ptxt = "THROUGHPUT REGRESSION %.2fx of the declared baseline (%s, flag below %.2fx)" % (
            perf["ratio"], "tokens/s" if perf["ratio_key"] == "tok_s" else "questions/s", perf["threshold"])
        rank = {"none": 0, "read": 1, "decide": 2}
        if rank[esc] < rank[PERF_ESCALATION]:
            esc = PERF_ESCALATION
        why_text = ptxt + ("; " + why_text if why_text else "")
    shards = shard_status(d, samples[-1]) if samples and state == "running" else None
    if shards and shards["note"] and shards["lost"]:
        notes.append("shards: " + shards["note"])
    pointers = []
    if esc != "none":
        if (state in ("failed", "stalled", "unknown") or flat_on or anomaly) and newest is not None:
            n = last_lines.get(newest[1], 0)
            if n:
                pointers.append({"path": newest[1], "line_start": max(1, n - 39), "line_end": n, "why": "tail of newest log"})
        if marker and state in ("failed", "unknown"):
            pointers.append({"path": marker["path"], "line_start": 1, "line_end": 5, "why": "terminal marker"})
        for s in out_sigs:
            if s["severity"] == "error" and len(pointers) < 5:
                ex = s["exemplar"]
                pointers.append({"path": ex["log"], "line_start": ex["line_start"], "line_end": ex["line_end"],
                                 "why": "error exemplar x%d" % s["count"]})
        if sus["total"]:
            kinds = ",".join(sorted(sus["by_kind"]))
            pointers.append({"path": rp, "json_paths": [i["path"] for i in sus["items"][:3]], "why": "suspicious: " + kinds})
    if perf_on:
        pj = os.path.join(d, perf["ratio_dir"], "perf.json") if perf["ratio_dir"] not in (None, ".") else os.path.join(d, "perf.json")
        pointers.insert(0, {"path": pj, "json_paths": ["$.window", "$.baseline", "$.ratio_to_baseline"],
                            "why": "throughput %.2fx of baseline" % perf["ratio"]})
    why = read_why(d, cfg)
    if why is None:
        why = inherited_why(run, cfg)
    inh = why.get("inherited_from") if why else None
    esc_before, expected_applied = esc, False
    # "expected": true downgrades only a run with a terminal marker (done/failed), an archived run, or a STALLED run (no marker and no
    # heartbeat: someone wrote the file to say the stop is deliberate). Running and unknown runs keep their escalation whatever the file
    # claims. A note alone never changes anything, and the watchdog never guesses which stalls are expected.
    if why and why["expected"] and (state in ("archived", "stalled") or (marker is not None and state in ("done", "failed"))):
        expected_applied = True
        if esc != "none":
            esc, why_text = "none", "expected=yes%s (was %s: %s)" % (" inherited from %s/%s" % (inh, why["file"]) if inh else "", esc_before, why_text)
    if progress is None and state in ("running", "stalled"):
        progress = {"done": None, "total": None, "percent": None, "rate_per_min": None, "window_s": None,
                    "eta_utc": None, "note": "no heartbeat samples", "counters": None, "fields": None}
    return {
        "id": run["id"], "path": d, "state": state, "condition": condition, "state_reason": reason, "escalation": esc, "escalation_reason": why_text,
        "tier": {k: tier[k] for k in ("name", "short", "source", "recheck_s", "stall_s")},
        "heartbeat_epoch": hb_ts, "heartbeat_utc": iso(hb_ts), "heartbeat_source": hb_src, "age_s": int(now - hb_ts) if hb_ts is not None else None,
        "marker": ({k: marker[k] for k in ("name", "path", "exit_code", "utc")} if marker else None),
        "progress": progress, "errors": errors, "suspicious_metrics": sus, "pointers": pointers[:6], "notes": notes, "why": why,
        "declared_total": tier.get("declared_total"), "uniform_cost": tier.get("uniform_cost", True), "total_anomaly": anomaly, "progress_flat": flat_info, "flat_reads": flat_reads, "flat_done": flat_done, "shards": shards,
        "perf": perf, "perf_regression": perf_on,
        "expected_applied": expected_applied,
        "expected_from": ({"kind": "inherited" if inh else "own", "id": inh, "dir": why.get("inherited_dir"), "file": why["file"]}
                          if expected_applied else None),
        "escalation_before_expected": esc_before if esc_before != esc else None,
        "logs": logs,
    }


# ----------------------------------------------------------------------------- host utilisation (NPU)
# npu-smi prints each chip on TWO lines. Line 1: "| 0  910B3 | OK | <power W>  <temp C>  <hugepages> |". Line 2:
# "| 0 | <bus id> | <AICore %> <mem used>/<mem total> <HBM used>/<HBM total> |" (HBM-Usage(MB) is the LAST pair). Below, one row per
# process: "| <npu> <chip> | <pid> | <name> | <MB> | ... |".
_NPU_L1 = re.compile(r"^\|\s*(\d+)\s+([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*(-?[\d.]+)\s+(-?\d+)\s")
_NPU_L2 = re.compile(r"^\|\s*(\d+)\s*\|\s*([0-9A-Fa-f:.]+)\s*\|\s*(\d+)\s+(\d+)\s*/\s*(\d+)\s+(\d+)\s*/\s*(\d+)\s*\|")
_NPU_PROC = re.compile(r"^\|\s*(\d+)\s+(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]*?)\s*\|\s*(\d+)\s*\|")
NPU_MAX_PS = 16 << 20


def parse_npu_smi(text):
    """One `npu-smi info` snapshot -> {"chips": [...], "procs": [...]}. Unrecognised lines are ignored."""
    chips, procs, pend = [], [], None
    for ln in text.splitlines():
        m = _NPU_L2.match(ln)
        if m and pend:
            chips.append({"npu": pend[0], "chip": int(m.group(1)), "name": pend[1], "health": pend[2], "power_w": pend[3],
                          "temp_c": pend[4], "bus_id": m.group(2), "aicore_pct": int(m.group(3)),
                          "hbm_used_mb": int(m.group(6)), "hbm_total_mb": int(m.group(7))})
            pend = None
            continue
        m = _NPU_PROC.match(ln)
        if m:
            procs.append({"npu": int(m.group(1)), "chip": int(m.group(2)), "pid": int(m.group(3)), "name": m.group(4),
                          "mem_mb": int(m.group(5))})
            continue
        m = _NPU_L1.match(ln)
        if m:
            pend = (int(m.group(1)), m.group(2), m.group(3), float(m.group(4)), int(m.group(5)))
    return {"chips": chips, "procs": procs}


_PROCMEM = re.compile(r"Process id:\s*(\d+)\s+Process name:\s*(.*?)\s+Process memory\(MB\):\s*(\d+)")


def parse_proc_mem(text):
    """`npu-smi info -t proc-mem -i N` -> list of {pid, name, mem_mb}. The fields have NO space after the colons. 'No process in device.'
    gives []. The caller must know the section was present: [] from a present section means 'nothing resident'."""
    return [{"pid": int(a), "name": b, "mem_mb": int(c)} for a, b, c in _PROCMEM.findall(text)]


def npu_script(cfg):
    n, gap = max(1, cfg.npu_samples), max(0.0, cfg.npu_sample_gap)
    return ('i=1; while [ $i -le %d ]; do echo "@@SAMPLE $i"; npu-smi info 2>&1; '
            'if [ $i -lt %d ]; then sleep %g; fi; i=$((i+1)); done; '
            'for n in $(npu-smi info -l 2>/dev/null | awk \'/NPU ID/ {print $NF}\'); do echo "@@PROC $n"; npu-smi info -t proc-mem -i $n 2>&1; done; '
            'echo "@@PS"; ps -eo pid=,args= 2>/dev/null | cut -c1-1500' % (n, n, gap))


def probe_npu(cfg):
    """Run npu-smi (over ssh to cfg.npu_host, or locally for 'local') and parse it. Never raises: returns {"ok": False, "reason"} on any
    failure (ssh missing, host down, timeout, no npu-smi, unparseable output). Gathers, in one ssh call: several `npu-smi info`
    snapshots (AICore, HBM), the resident processes per NPU from `npu-smi info -t proc-mem` (the claim signal), and a ps listing that is
    kept only in memory, only to map the process ids to run directories; command lines are never stored or printed."""
    import subprocess
    script = npu_script(cfg)
    if cfg.npu_host == "local":
        cmd = ["bash", "-c", script]
    else:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "ServerAliveInterval=5", cfg.npu_host, script]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=cfg.npu_timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "npu probe timed out after %gs" % cfg.npu_timeout}
    except OSError as e:
        return {"ok": False, "reason": "npu probe could not start: %s" % redact(str(e))[:80]}
    out = r.stdout[:NPU_MAX_PS].decode("utf-8", "replace")
    if r.returncode != 0 and "@@SAMPLE" not in out:
        return {"ok": False, "reason": "ssh/npu-smi failed (rc %d): %s" % (
            r.returncode, redact(" ".join(r.stderr.decode("utf-8", "replace").split()))[:100] or "no message")}
    rest, _, ps_txt = out.partition("@@PS")
    head, _, proc_txt = rest.partition("@@PROC")
    samples = []
    for sec in head.split("@@SAMPLE")[1:]:
        snap = parse_npu_smi(sec)
        if snap["chips"]:
            samples.append(snap)
    if not samples:
        first = next((x.strip() for x in head.splitlines() if x.strip() and not x.startswith("@@")), "")
        return {"ok": False, "reason": "no chips parsed from npu-smi output (first line: %s)" % (redact(first)[:70] or "empty")}
    procmem = {}
    for sec in ("@@PROC" + proc_txt).split("@@PROC")[1:] if proc_txt else []:
        m = re.match(r"\s*(\d+)\s*\n", sec)
        if m:
            procmem[int(m.group(1))] = parse_proc_mem(sec)
    ps = {}
    for ln in ps_txt.splitlines():
        m = re.match(r"\s*(\d+)\s+(.*)$", ln)
        if m:
            ps[int(m.group(1))] = m.group(2)
    return {"ok": True, "samples": samples, "procmem": procmem, "ps": ps, "t": time.time()}


_PATHTOK = re.compile(r"/[^\s'\"=:,;|()<>]+")


def claim_runs(args, by_path):
    """Run ids whose directory is named in a process command line: each absolute path token is walked up through its parents and the
    first (most specific) directory that is a known run claims the process."""
    found = set()
    for tok in _PATHTOK.findall(args or ""):
        p = os.path.normpath(tok)
        while p and p != "/":
            if p in by_path:
                found.add(by_path[p])
                break
            p = os.path.dirname(p)
    return found


NPU_HIST_KEEP_S = 6 * 3600


def load_npu_history(cfg):
    try:
        with open(os.path.join(cfg.npu_history_from or cfg.out_dir, "npu_history.json"), "r", encoding="utf-8") as f:
            o = json.load(f)
        return {int(k): [e for e in v if isinstance(e, list) and len(e) == 4] for k, v in o.items()}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def save_npu_history(cfg, hist):
    try:
        os.makedirs(cfg.out_dir, exist_ok=True)
        atomic_write(os.path.join(cfg.out_dir, "npu_history.json"), json.dumps({str(k): v for k, v in hist.items()}) + "\n")
    except OSError:
        pass


def streak(entries, cfg, pred):
    """Trailing run of history entries [ts, mean, max, claimed] for which pred(entry) holds, broken by a gap longer than three ticks
    (the watchdog was not looking). -> (passes, seconds from its first entry to the newest)."""
    gap_max = max(3 * cfg.interval, 1800.0)
    n, first, prev = 0, None, None
    for e in reversed(entries):
        if not pred(e) or (prev is not None and prev - e[0] > gap_max):
            break
        n, first, prev = n + 1, e[0], e[0]
    return (n, entries[-1][0] - first) if n else (0, 0.0)


def window_passes(entries, t, cfg):
    """The history entries [ts, pass mean, max, claimed] the utilisation verdict is computed from: the trailing stretch of CLAIMED
    passes that fall inside the last --npu-window-seconds. Unclaimed passes are not utilisation of the claimed chip and end the
    stretch; the first claimed pass after an unclaimed one is warm-up (a container loading weights reads 0 %) and is excluded, as is
    anything older than the window. Each entry is the mean of one pass's snapshots, so the passes weigh equally."""
    stretch = []
    for e in reversed(entries):
        if not e[3]:
            break
        stretch.append(e)
    stretch.reverse()
    if len(stretch) < len(entries) and stretch:
        stretch = stretch[1:]
    return [e for e in stretch if t - e[0] <= cfg.npu_window_seconds]


ALLOCATION_NAME = "CHIP-ALLOCATION.json"


def load_allocation(cfg):
    """Chip OWNERSHIP, from the allocation file only (read only). -> {"ok", "path", "reason", "updated_utc", "updated_by", "owners":
    {chip: entry}, "dup": {chips listed twice}, "free": {chips}, "pending": {chip: [who]}}. ok is False when the file is missing or
    does not parse into the expected shape; nothing is then assumed about any chip."""
    path = cfg.chip_allocation or os.path.join(os.path.abspath(cfg.root[0]), ALLOCATION_NAME)
    out = {"ok": False, "path": path, "reason": None, "updated_utc": None, "updated_by": None, "owners": {}, "dup": set(), "free": set(),
           "pending": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            o = json.load(f)
    except OSError as e:
        out["reason"] = "cannot read: %s" % redact(str(e))[:80]
        return out
    except ValueError as e:
        out["reason"] = "not valid JSON: %s" % str(e)[:60]
        return out
    isint = lambda v: isinstance(v, int) and not isinstance(v, bool)   # noqa: E731
    if not isinstance(o, dict) or not isinstance(o.get("allocation"), list):
        out["reason"] = "no 'allocation' list"
        return out
    for e in o["allocation"]:
        if not isinstance(e, dict) or not isint(e.get("chip")) or not (isinstance(e.get("owner"), str) and e["owner"].strip()):
            out["reason"] = "allocation entry without an integer chip and an owner: %s" % redact(json.dumps(e))[:60]
            return out
        if e["chip"] in out["owners"]:
            out["dup"].add(e["chip"])
        out["owners"].setdefault(e["chip"], e)
    fr = o.get("free", [])
    if not isinstance(fr, list):
        out["reason"] = "'free' is not a list"
        return out
    for e in fr:
        c = e.get("chip") if isinstance(e, dict) else e
        if not isint(c):
            out["reason"] = "free entry without an integer chip: %s" % redact(json.dumps(e))[:60]
            return out
        out["free"].add(c)
    for e in o.get("pending_claims") or []:
        if isinstance(e, dict):
            who = e.get("who") if isinstance(e.get("who"), str) else "unnamed claimant"
            chips = e.get("chips") if isinstance(e.get("chips"), list) else [e.get("chip")]
            for c in chips:
                if isint(c):
                    out["pending"].setdefault(c, []).append(who)
    out["updated_utc"] = o.get("updated_utc") if isinstance(o.get("updated_utc"), str) else None
    out["updated_by"] = o.get("updated_by") if isinstance(o.get("updated_by"), str) else None
    out["ok"] = True
    return out


def chip_ownership(alloc, npu_id):
    """-> (ownership word, entry or None): owned | free | conflict (listed twice, or both owned and free) | unlisted (the file says
    neither) | unknown (the file could not be read). Never derived from a sample."""
    if not alloc["ok"]:
        return "unknown", None
    ent = alloc["owners"].get(npu_id)
    if ent is not None and (npu_id in alloc["free"] or npu_id in alloc["dup"]):
        return "conflict", ent
    if ent is not None:
        return "owned", ent
    return ("free", None) if npu_id in alloc["free"] else ("unlisted", None)


def analyse_npu(raw, runs, queued, cfg, hist=None):
    """Raw probe -> the digest's `npu` block. Two things per chip, kept apart and never merged into one word:
      OWNERSHIP (who may use the chip) comes only from CHIP-ALLOCATION.json: owned | free | conflict | unlisted | unknown (file unreadable).
        A sample cannot establish that a chip is free: a chip between shards reads 0 % with baseline HBM and is still owned.
      ACTIVITY (what the chip is doing) comes only from the samples: no-process (no resident process, baseline HBM) | quiet (a process,
        near-zero AICore, not yet long enough to mean anything) | wedged? (near-zero for --npu-wedged-passes passes spanning
        --npu-wedged-seconds) | low | busy (window mean below / at or above --npu-low-pct, informational: a launch-bound kernel runs
        healthy at 9-22 %) | unknown (fewer than --npu-min-passes claimed passes in the window).
    Flags combine the two without merging them: an OWNED chip with no process is 'idle, owner X' (wasted capacity, never available); a
    chip the file lists FREE and that has no process is 'free and unused' (decide while work runs or is queued); a FREE chip with a process
    is unrecorded use; a chip the file does not list, lists twice, or a file that cannot be read gives 'ownership unknown'."""
    out = {"available": False, "reason": None, "host": cfg.npu_host, "sampled_utc": None, "samples": 0, "chips": [], "no_process": [],
           "wedged": [], "quiet": [], "low": [], "running_runs": 0, "queued_runs": 0, "flags": [], "escalation": "none",
           "low_pct": cfg.npu_low_pct, "unknown": [], "window_s": cfg.npu_window_seconds, "min_passes": cfg.npu_min_passes,
           "owned_idle": [], "owned_idle_long": [], "free_unused": [], "ownership_unknown": [], "allocation": None,
           "owned_idle_decide_s": cfg.npu_owned_idle_seconds, "owned_idle_decide_passes": cfg.npu_owned_idle_passes}
    alloc = load_allocation(cfg)
    out["allocation"] = {"ok": alloc["ok"], "path": alloc["path"], "reason": alloc["reason"], "updated_utc": alloc["updated_utc"],
                         "updated_by": alloc["updated_by"], "allocated": sorted(alloc["owners"]), "free": sorted(alloc["free"]),
                         "pending": {str(k): v for k, v in sorted(alloc["pending"].items())}}
    if not raw.get("ok"):
        out["reason"] = raw.get("reason") or "unavailable"
        return out
    snaps = raw["samples"]
    last = snaps[-1]
    by_path = {r["path"]: r["id"] for r in runs}
    state_of = {r["id"]: r["state"] for r in runs}
    table = {}
    for pr in last["procs"]:
        table.setdefault(pr["npu"], {})[pr["pid"]] = pr
    h = hist if hist is not None else {}
    chips = []
    for c in last["chips"]:
        key = (c["npu"], c["chip"])
        vals = [x["aicore_pct"] for s_ in snaps for x in s_["chips"] if (x["npu"], x["chip"]) == key]
        mean = sum(vals) / float(len(vals))
        procs = dict(table.get(c["npu"], {}))
        for pr in raw.get("procmem", {}).get(c["npu"], []):
            procs.setdefault(pr["pid"], pr)
        pl, claimed_runs = [], set()
        for pid, pr in sorted(procs.items()):
            ids = claim_runs(raw["ps"].get(pid), by_path)
            claimed_runs |= ids
            pl.append({"pid": pid, "name": pr["name"], "mem_mb": pr["mem_mb"], "runs": sorted(ids)})
        resident = bool(pl) or c["hbm_used_mb"] > cfg.npu_idle_hbm_mb
        hl = h.setdefault(c["npu"], [])
        hl.append([raw["t"], round(mean, 1), max(vals), resident])
        hl[:] = [e for e in hl if raw["t"] - e[0] <= NPU_HIST_KEEP_S][-48:]
        wpass = window_passes(hl, raw["t"], cfg)
        wmean = round(sum(e[1] for e in wpass) / float(len(wpass)), 1) if wpass else None
        qn, qs = streak(hl, cfg, lambda e: e[3] and e[2] <= cfg.npu_near_zero_pct)
        un, us = streak(hl, cfg, lambda e: not e[3])
        if not resident:
            st = "no-process"
        elif max(vals) <= cfg.npu_near_zero_pct:
            st = "wedged?" if (qn >= cfg.npu_wedged_passes and qs >= cfg.npu_wedged_seconds) else "quiet"
        elif len(wpass) < cfg.npu_min_passes:
            st = "unknown"           # too few claimed passes in the window to say anything: never "low" on thin evidence
        elif wmean < cfg.npu_low_pct:
            st = "low"
        else:
            st = "busy"
        own, ent = chip_ownership(alloc, c["npu"])
        chips.append({"npu": c["npu"], "chip": c["chip"], "health": c["health"], "name": c["name"],
                      "ownership": own, "owner": ent["owner"] if ent else None, "owner_run": ent.get("run") if ent else None,
                      "release_when": ent.get("release_when") if ent else None, "pending_claims": alloc["pending"].get(c["npu"], []),
                      "activity": st, "resident": resident,
                      "aicore_last": vals[-1], "aicore_pct": round(mean, 1), "aicore_samples": vals,
                      "aicore_window_pct": wmean, "window_passes": len(wpass), "window_s": cfg.npu_window_seconds,
                      "aicore_recent_passes": [[iso(e[0]), e[1]] for e in hl[-6:]], "passes_seen": len(hl),
                      "quiet_passes": qn if st in ("quiet", "wedged?") else 0, "quiet_s": int(qs) if st in ("quiet", "wedged?") else 0,
                      "no_process_passes": un if st == "no-process" else 0, "no_process_s": int(us) if st == "no-process" else 0,
                      "hbm_used_mb": c["hbm_used_mb"], "hbm_total_mb": c["hbm_total_mb"], "power_w": c["power_w"], "temp_c": c["temp_c"],
                      "claimed_by": sorted(claimed_runs), "claimed_state": {i: state_of.get(i) for i in sorted(claimed_runs)},
                      "processes": pl[:8], "n_processes": len(pl), "processes_without_run": sum(1 for p_ in pl if not p_["runs"])})
    n_run = sum(1 for r in runs if r["state"] == "running")
    n_q = len(queued)
    names = {k: [c["npu"] for c in chips if c["activity"] == v] for k, v in
             (("no_process", "no-process"), ("wedged", "wedged?"), ("quiet", "quiet"), ("low", "low"), ("unknown", "unknown"))}
    out.update(names)
    out["owned_idle"] = [c["npu"] for c in chips if c["activity"] == "no-process" and c["ownership"] == "owned"]
    out["free_unused"] = [c["npu"] for c in chips if c["activity"] == "no-process" and c["ownership"] == "free"]
    out["ownership_unknown"] = [c["npu"] for c in chips if c["ownership"] in ("unknown", "unlisted", "conflict")]
    out.update({"available": True, "sampled_utc": iso(raw["t"]), "samples": len(snaps), "chips": chips,
                "running_runs": n_run, "queued_runs": n_q})

    def ids(lst):
        return ",".join(str(x) for x in lst)

    def since(c):
        return ("for >=%s (%d passes)" % (human_age(c["no_process_s"]), c["no_process_passes"])) if c["no_process_passes"] > 1 else "first seen this pass"
    by = {c["npu"]: c for c in chips}
    work = n_run + n_q
    if not alloc["ok"]:
        out["flags"].append({"kind": "ownership_unknown", "escalation": "read", "chips": [c["npu"] for c in chips], "text":
                             "CHIP OWNERSHIP UNKNOWN: %s is unreadable (%s). Utilisation below is from samples only; a sample can never "
                             "show that a chip is free, so none is reported free" % (alloc["path"], alloc["reason"])})
    else:
        odd = [c for c in chips if c["ownership"] in ("unlisted", "conflict")]
        if odd:
            out["flags"].append({"kind": "ownership_unknown", "escalation": "read", "chips": [c["npu"] for c in odd], "text":
                                 "CHIP OWNERSHIP UNKNOWN for chip %s: %s lists %s; nothing is assumed free" % (
                                     ids([c["npu"] for c in odd]), os.path.basename(alloc["path"]),
                                     "no owner and no free entry" if all(c["ownership"] == "unlisted" for c in odd) else "a chip twice or as both owned and free")})
    long_ = [k for k in out["owned_idle"] if by[k]["no_process_s"] >= cfg.npu_owned_idle_seconds
             and by[k]["no_process_passes"] >= cfg.npu_owned_idle_passes]
    short = [k for k in out["owned_idle"] if k not in long_]
    out["owned_idle_long"] = long_

    def idle_detail(ks):
        return "; ".join("chip %d idle, owner %s%s, %s" % (
            k, _clip(by[k]["owner"], 40), " (%s)" % by[k]["owner_run"] if by[k]["owner_run"] else "", since(by[k])) for k in ks)
    if long_:
        out["flags"].append({"kind": "owned_idle_long", "escalation": "decide", "chips": long_, "text":
                             "NPU OWNED BUT IDLE FOR A LONG STRETCH (>= %s and >= %d passes; owned, not available): %s. Either the owner finished and "
                             "did not release it in the allocation file, or its job is dead: a decision, not a reading" % (
                                 human_age(cfg.npu_owned_idle_seconds), cfg.npu_owned_idle_passes, idle_detail(long_))})
    if short:
        out["flags"].append({"kind": "owned_idle", "escalation": "read", "chips": short, "text":
                             "NPU OWNED BUT IDLE (no resident process, baseline HBM; owned, not available): %s. The allocation file, not this "
                             "sample, says who may use it; a chip between shards also reads like this" % idle_detail(short)})
    if out["free_unused"]:
        det = ", ".join("%d %s" % (k, since(by[k])) for k in out["free_unused"])
        out["flags"].append({"kind": "free_unused", "escalation": "decide" if work else "read", "chips": out["free_unused"], "text":
                             "NPU FREE per %s and unused (no resident process) while %d run(s) running and %d queued: chip %s. A container "
                             "still starting is not yet visible, so a first sighting may be one" % (os.path.basename(alloc["path"]), n_run, n_q, det)})
    fin = [c["npu"] for c in chips if c["ownership"] == "free" and c["resident"]]
    if fin:
        out["flags"].append({"kind": "free_in_use", "escalation": "read", "chips": fin, "text":
                             "NPU LISTED FREE but has a resident process or HBM above baseline: chip %s (use not recorded in the allocation file)" % ids(fin)})
    if out["wedged"]:
        det = ", ".join("%d for >=%s (%d passes)" % (c["npu"], human_age(c["quiet_s"]), c["quiet_passes"]) for c in chips if c["activity"] == "wedged?")
        out["flags"].append({"kind": "possibly_wedged", "escalation": "read", "chips": out["wedged"], "text":
                             "NPU HAS A PROCESS BUT NEAR-ZERO AICore (<=%g%%) possibly wedged or starved: chip %s" % (cfg.npu_near_zero_pct, det)})
    if out["low"]:
        out["flags"].append({"kind": "claimed_low_info", "escalation": "none", "chips": out["low"], "text":
                             "info: chips %s below %g%% mean AICore over the last %s (%s); not a fault by itself, judge by throughput against the run's own baseline" % (
                                 ids(out["low"]), cfg.npu_low_pct, human_age(cfg.npu_window_seconds),
                                 ", ".join("%d=%g%% over %d passes" % (c["npu"], c["aicore_window_pct"], c["window_passes"]) for c in chips if c["activity"] == "low"))})
    acts = [f["escalation"] for f in out["flags"] if f["escalation"] != "none"]
    out["escalation"] = "decide" if "decide" in acts else "read" if acts else "none"
    return out


def npu_fragment(npu):
    """Compact status for the summary line: always present, a few dozen bytes. Ownership words (owned-idle, FREE, OWNERSHIP UNKNOWN) come
    from the allocation file; activity words (resident, low, util unknown, wedged?) from the samples. Chip numbers are always labelled."""
    if not npu:
        return ""
    if not npu["available"]:
        return " | npu n/a"
    n = len(npu["chips"])
    ids = lambda l: ",".join(str(x) for x in l)   # noqa: E731
    bits = []
    if npu.get("ownership_unknown"):
        al = npu.get("allocation") or {}
        bits.append("OWNERSHIP UNKNOWN chips %s%s" % (ids(npu["ownership_unknown"]), "" if al.get("ok") else " (%s unreadable)" % ALLOCATION_NAME))
    if npu.get("owned_idle"):
        lg = npu.get("owned_idle_long") or []
        bits.append("owned but idle chips %s%s" % (ids(npu["owned_idle"]), " (chips %s idle >= %s: decide)" % (
            ids(lg), human_age(npu.get("owned_idle_decide_s") or 0)) if lg else ""))
    if npu.get("free_unused"):
        bits.append("FREE per file and unused chips %s (%d run, %d queued)" % (ids(npu["free_unused"]), npu["running_runs"], npu["queued_runs"]))
    if npu["wedged"]:
        bits.append("wedged? chips %s" % ids(npu["wedged"]))
    win = human_age(npu.get("window_s") or 0)
    if npu["low"]:
        bits.append("low chips %s (mean AICore over %s window)" % (ids(npu["low"]), win))
    if npu.get("unknown"):
        who = "all chips" if len(npu["unknown"]) == n else "chips %s" % ids(npu["unknown"])
        now = ", ".join("%d=%g%%" % (c["npu"], c["aicore_pct"]) for c in npu["chips"] if c["activity"] == "unknown")
        bits.append("util unknown on %s (<%d passes in %s window, no usable history; this pass's mean only: %s)" % (
            who, npu.get("min_passes") or 0, win, now))
    tail = ", AICore window %s" % win          # every pass states the window its utilisation verdict used
    if not bits:
        return " | npu %d/%d resident, owners per file%s" % (n - len(npu["no_process"]), n, tail)
    return " | npu " + "; ".join(bits) + " of %d%s" % (n, tail)


def _aicore_cell(c):
    prev = [e[1] for e in c["aicore_recent_passes"][:-1]][-3:]
    cell = "%g%%" % c["aicore_last"] + (" [%s]" % " ".join("%g" % v for v in prev) if prev else "")
    if not c["resident"]:
        return cell
    if c.get("aicore_window_pct") is not None and c["activity"] != "unknown":
        win = "%g%%/%s n=%d" % (c["aicore_window_pct"], human_age(c["window_s"]), c["window_passes"])
    else:
        win = "unknown n=%d/%s, this pass mean %g%%" % (c.get("window_passes", 0), human_age(c.get("window_s") or 0), c["aicore_pct"])
    return cell + " win " + win


def _owner_cell(c):
    o = c["ownership"]
    if o == "owned":
        txt = "%s%s" % (_clip(c["owner"], 30), " (%s)" % _clip(c["owner_run"], 30) if c["owner_run"] else "")
    elif o == "free":
        txt = "FREE per file"
    elif o == "unknown":
        txt = "ownership unknown"
    else:
        txt = "ownership unknown (%s)" % o
    if c["pending_claims"]:
        txt += "; pending: " + _clip(", ".join(c["pending_claims"]), 40)
    return txt


def npu_block_lines(npu, level):
    """Level 1: the escalation line(s) (or the reason the probe failed). Level 2: also the per-chip table."""
    if not npu:
        return []
    ts = (npu.get("sampled_utc") or "")[11:16]
    if not npu["available"]:
        return ["NPU utilisation unavailable (%s): %s" % (npu["host"], _clip(npu["reason"], 140))]
    lines = ["- [%s] %s" % (f["escalation"], _clip(f["text"], 230)) if f["escalation"] != "none" else "- %s" % _clip(f["text"], 200)
             for f in npu["flags"]]
    al = npu.get("allocation") or {}
    if al.get("ok"):
        lines.append("Ownership: from %s (updated %s by %s); activity: from samples, AICore window %s" % (
            os.path.basename(al["path"]), al.get("updated_utc") or "?", _clip(al.get("updated_by") or "?", 40), human_age(npu.get("window_s") or 0)))
    if not npu["flags"]:
        lines.append("NPU: every chip has a resident process and none is near-zero for long (%s)" % ts)
    if level >= 2:
        lines += ["| chip | owner (allocation file) | AICore [earlier passes] win | HBM GiB | activity (samples) | process claimed by |", "|---|---|---|---|---|---|"]
        for c in npu["chips"]:
            cl = list(c["claimed_by"])
            who = ", ".join(_clip(x, 36) + ("" if c["claimed_state"].get(x) == "running" else "(%s)" % c["claimed_state"].get(x)) for x in cl[:2]) \
                + (" +%d" % (len(cl) - 2) if len(cl) > 2 else "")
            if not cl:
                who = ("%d proc, no run dir" % c["n_processes"]) if c["n_processes"] else ("HBM only" if c["resident"] else "-")
            st = c["activity"] + (" %s" % human_age(c["quiet_s"]) if c["activity"] in ("quiet", "wedged?") and c["quiet_s"] else "")
            lines.append("| %d | %s | %s | %.1f/%.0f | %s | %s |" % (c["npu"], _owner_cell(c), _aicore_cell(c), c["hbm_used_mb"] / 1024.0,
                                                                  c["hbm_total_mb"] / 1024.0, st, who))
    return lines


# ----------------------------------------------------------------------------- retention of flagged passes
# digest.json is rewritten every pass, so evidence that lives only there has a ten-minute lifetime. A pass that carries ANY flag is
# copied to <out-dir>/_retained/. This preserves pointers and clustered signatures; it does NOT preserve the logs the pointers name
# (CLAUDE.md 7.1: the digest carries pointers, never the evidence). See tools/README.md: retention is half of a pair.
RETAIN_DIR = "_retained"
RETAIN_NOTE = ("A retained digest preserves what the digest carries: run states, marker names/exit codes/timestamps, suspicious-metric "
               "paths and values, and clustered error-signature exemplars with their pointers. It does NOT preserve the log files or "
               "report files those pointers name; a relaunch may have deleted them. Evidence is preserved only if the run directory "
               "was also kept (a relaunch must move a directory holding a terminal marker to <name>.crash-<utc>/, never delete it).")


def pass_flags(dg):
    """The flags a pass carries, as {key: kind}. Any flag of any kind, explained or not: a dispositioned flag is still a flag. Kinds:
    state:failed|stalled|unknown, suspicious:<kind> (exact 0/1, identical cells, low n, non-finite: suspicious SUCCESSES count,
    suppressed expected-degenerate values do not), error (error-severity signature, keyed by signature), perf_regression, progress_flat,
    total_anomaly, escalation:<level> (any escalation, or the one a WHY disposition removed), npu:<kind> (escalating NPU flags only;
    the informational 'claimed low' line and warning-only signatures are not flags)."""
    out = {}
    for r in dg["runs"]:
        rid = r["id"]
        if r["state"] in ("failed", "stalled", "unknown"):
            out["state:%s:%s" % (r["state"], rid)] = "state:" + r["state"]
        for it in r["suspicious_metrics"]["items"]:
            out["suspicious:%s:%s:%s" % (it["kind"], rid, it["path"])] = "suspicious:" + it["kind"]
        if r["suspicious_metrics"]["total"] and not r["suspicious_metrics"]["items"]:
            out["suspicious:?:%s" % rid] = "suspicious:?"
        for sg in r["errors"]["signatures"]:
            if sg["severity"] == "error":
                out["error:%s:%s" % (rid, hashlib.md5(sg["signature"].encode()).hexdigest()[:8])] = "error"
        if r.get("perf_regression"):
            out["perf_regression:" + rid] = "perf_regression"
        if r.get("progress_flat"):
            out["progress_flat:" + rid] = "progress_flat"
        if r.get("total_anomaly"):
            out["total_anomaly:" + rid] = "total_anomaly"
        lvl = r["escalation"] if r["escalation"] != "none" else r.get("escalation_before_expected")
        if lvl and lvl != "none":
            out["escalation:%s:%s" % (lvl, rid)] = "escalation:" + lvl
    for it in (dg.get("obligations") or {}).get("items", []):
        if it["status"] in ("due", "invalid"):
            out["obligation_%s:%s" % (it["status"], it["id"])] = "obligation_" + it["status"]
    for f in (dg.get("obligations") or {}).get("files", []):
        if not f["ok"]:
            out["obligation_file:" + f["path"]] = "obligation_file"
    npu = dg.get("npu") or {}
    for f in npu.get("flags", []):
        if f["escalation"] != "none":
            out["npu:%s:%s" % (f["kind"], ",".join(str(c) for c in f["chips"]))] = "npu:" + f["kind"]
    return out


def _retain_files(rdir):
    try:
        names = sorted(n for n in os.listdir(rdir) if n.startswith("digest-") and n.endswith((".json", ".md")))
    except OSError:
        return []
    stems = sorted({n.rsplit(".", 1)[0] for n in names})
    out = []
    for st in stems:
        fs = [os.path.join(rdir, n) for n in names if n.rsplit(".", 1)[0] == st]
        try:
            out.append((st, fs, sum(os.path.getsize(f) for f in fs)))
        except OSError:
            pass
    return out


def retain_pass(cfg, dg, md, now):
    """Decide and write the retention for this pass. Returns a small status dict (also put into digest.json as `retention`).
    Trigger, with a non-empty flag set: (a) a flag key appears that was not in the previous pass and was not retained within
    --retain-flap-seconds (a flapping flag does not retain every tick); (b) the newest retained copy is older than
    --retain-refresh-hours (a long-lived flag is re-captured, so its pointers and exemplars do not go stale). A flag that clears
    does not trigger by itself. State lives in <out-dir>/_retained/index.json, so a restart neither forgets nor repeats. Bounded:
    oldest copies are deleted beyond --retain-max copies or --retain-max-mb."""
    st = {"enabled": True, "flags": 0, "retained": None, "trigger": None, "kept": 0, "dir": os.path.join(cfg.out_dir, RETAIN_DIR)}
    if cfg.no_retain:
        st["enabled"] = False
        return st
    flags = pass_flags(dg)
    st["flags"] = len(flags)
    rdir = st["dir"]
    os.makedirs(rdir, exist_ok=True)
    lock = open(os.path.join(rdir, ".lock"), "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ip = os.path.join(rdir, "index.json")
        try:
            with open(ip, "r", encoding="utf-8") as f:
                idx = json.load(f)
        except (OSError, ValueError):
            idx = {}
        prev = set(idx.get("last_flags", []))
        seen = {k: v for k, v in idx.get("seen", {}).items() if now - v <= 2 * cfg.retain_refresh_hours * 3600}
        last_ts = idx.get("last_retained_ts")
        new = sorted(k for k in flags if k not in prev and (k not in seen or now - seen[k] > cfg.retain_flap_seconds))
        trigger = None
        if flags and new:
            trigger = "new_flags"
        elif flags and (last_ts is None or now - last_ts > cfg.retain_refresh_hours * 3600):
            trigger = "refresh"
        if trigger:
            stem = "digest-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now))
            n = 1
            while os.path.exists(os.path.join(rdir, stem + ".json")):
                n += 1
                stem = "digest-%s-%d" % (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now)), n)
            kinds = {}
            for k in flags.values():
                kinds[k] = kinds.get(k, 0) + 1
            gone = sorted(prev - set(flags))
            meta = {
                "retained_utc": iso(now), "trigger": trigger,
                "why": ("%d flag(s) not present in the previous pass: %s" % (len(new), ", ".join(new[:6]) + (", ..." if len(new) > 6 else ""))
                        if trigger == "new_flags" else
                        "refresh: %d flag(s) still present and the newest retained copy is older than %g h" % (len(flags), cfg.retain_refresh_hours)),
                "new_flags": new[:100], "new_flags_total": len(new), "cleared_since_previous_pass": gone[:50],
                "flags_total": len(flags), "flag_kinds": dict(sorted(kinds.items())), "previous_retained": idx.get("last_retained"),
                "NOT_PRESERVED": RETAIN_NOTE,
            }
            atomic_write(os.path.join(rdir, stem + ".json"), json.dumps(dict([("retention", meta)] + list(dg.items())), indent=1) + "\n")
            head = ["<!-- RETAINED digest %s. Trigger: %s. %s -->" % (meta["retained_utc"], trigger, meta["why"]),
                    "<!-- %s -->" % RETAIN_NOTE]
            atomic_write(os.path.join(rdir, stem + ".md"), "\n".join(head) + "\n" + md)
            idx["last_retained_ts"], idx["last_retained"] = now, stem + ".json"
            for k in new:
                seen[k] = now
            st["retained"], st["trigger"] = stem + ".json", trigger
        idx["last_flags"], idx["seen"] = sorted(flags), seen
        atomic_write(ip, json.dumps(idx) + "\n")
        files = _retain_files(rdir)
        total = sum(f[2] for f in files)
        while files and (len(files) > cfg.retain_max or total > cfg.retain_max_mb * (1 << 20)) and len(files) > 1:
            stem, fs, sz = files.pop(0)
            for f in fs:
                try:
                    os.unlink(f)
                except OSError:
                    pass
            total -= sz
        st["kept"], st["bytes"] = len(files), total
    finally:
        lock.close()
    return st


# ----------------------------------------------------------------------------- obligations (absent artefacts)
# Neither a failure nor a stall can describe a product that was never produced. obligations.json declares what is owed, the artefact that
# discharges it and the event that makes it due; the watchdog reads the file and knows nothing about any particular round.
OBL_FILE = "obligations.json"
OBL_SCHEMA = 1
OBL_STATE = "obligations_state.json"
OBL_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
OBL_PREDICATES = ("exists", "nonempty", "min_lines", "matches")
OBL_MAX = 200
OBL_SHOW = 12                 # due/invalid lines and pending lines listed in digest.md, each; the rest are counted


def _obl_glob(base, pat):
    p = pat if os.path.isabs(pat) else os.path.join(base, pat)
    return sorted(glob.glob(p, recursive=True))[:200]


def _nonempty(path):
    try:
        if os.path.isdir(path):
            with os.scandir(path) as it:
                return next(it, None) is not None
        return os.path.getsize(path) > 0
    except OSError:
        return False


def _enough_lines(path, n):
    try:
        got = 0
        with open(path, "rb") as f:
            for _ in f:
                got += 1
                if got >= n:
                    return True
    except OSError:
        pass
    return False


def _has_match(path, rx):
    try:
        read = 0
        with open(path, "rb") as f:
            for ln in f:
                read += len(ln)
                if rx.search(ln.decode("utf-8", "replace")):
                    return True
                if read > (8 << 20):
                    break
    except OSError:
        pass
    return False


def eval_pred(spec, base, now, depth=0):
    """(satisfied, evidence text) for one predicate spec; raises ValueError for a spec that cannot be evaluated (the caller reports the
    obligation as invalid: an obligation that silently never fires is the failure this block exists to prevent).
    spec: {"path": glob, "predicate": exists|nonempty(default)|min_lines|matches, "n": int, "pattern": regex}  |  {"after_utc": ISO}
          |  {"any": [spec, ...]}  |  {"all": [spec, ...]}.  Relative globs resolve against the directory of obligations.json."""
    if not isinstance(spec, dict) or depth > 3:
        raise ValueError("predicate must be a JSON object, nested at most 3 deep")
    keys = [k for k in ("any", "all", "after_utc", "path") if k in spec]
    if len(keys) != 1:
        raise ValueError("predicate needs exactly one of path, after_utc, any, all (has %s)" % (keys or "none"))
    k = keys[0]
    if k in ("any", "all"):
        subs = spec[k]
        if not isinstance(subs, list) or not subs:
            raise ValueError("%s needs a non-empty list" % k)
        res = [eval_pred(x, base, now, depth + 1) for x in subs]        # evaluate all: a broken member must always surface
        ok = any(r[0] for r in res) if k == "any" else all(r[0] for r in res)
        return ok, "; ".join(r[1] for r in res if r[0]) if k == "any" else "; ".join(r[1] for r in res)
    if k == "after_utc":
        m = TS_RE.fullmatch(spec["after_utc"]) if isinstance(spec["after_utc"], str) else None
        t = parse_ts(m) if m else None
        if t is None:
            raise ValueError("after_utc must be an ISO-8601 timestamp such as 2026-11-01T00:00:00Z")
        return now >= t, "after %s" % spec["after_utc"]
    pat = spec["path"]
    if not isinstance(pat, str) or not pat.strip():
        raise ValueError("path must be a non-empty string (glob; relative to the obligations file)")
    pred = spec.get("predicate", "nonempty")
    if pred not in OBL_PREDICATES:
        raise ValueError("unknown predicate %s (expected one of %s)" % (json.dumps(pred)[:30], "|".join(OBL_PREDICATES)))
    files = _obl_glob(base, pat)
    if pred == "exists":
        ok = [f for f in files if os.path.exists(f)]
    elif pred == "nonempty":
        ok = [f for f in files if _nonempty(f)]
    elif pred == "min_lines":
        n = spec.get("n")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("min_lines needs a positive integer n")
        ok = [f for f in files if os.path.isfile(f) and _enough_lines(f, n)]
    else:
        try:
            rx = re.compile(spec.get("pattern"))
        except (re.error, TypeError):
            raise ValueError("matches needs a valid regex in pattern")
        ok = [f for f in files if os.path.isfile(f) and _has_match(f, rx)]
    return bool(ok), ("%s (%s)" % (ok[0], pred)) if ok else "no file matches %s (%s)" % (pat, pred)


def describe_pred(spec):
    if not isinstance(spec, dict):
        return "?"
    if "any" in spec or "all" in spec:
        k = "any" if "any" in spec else "all"
        lst = spec[k] if isinstance(spec[k], list) else []
        return "%s of [%s]" % (k, "; ".join(describe_pred(x) for x in lst[:4]) + ("; ..." if len(lst) > 4 else ""))
    if "after_utc" in spec:
        return "time after %s" % spec["after_utc"]
    extra = (" n=%s" % spec.get("n")) if spec.get("predicate") == "min_lines" else (" /%s/" % spec.get("pattern")) if spec.get("predicate") == "matches" else ""
    return "%s %s%s" % (spec.get("predicate", "nonempty"), spec.get("path"), extra)


def load_obl_state(cfg):
    try:
        with open(os.path.join(cfg.out_dir, OBL_STATE), "r", encoding="utf-8") as f:
            o = json.load(f)
        return o if isinstance(o, dict) else {}
    except (OSError, ValueError):
        return {}


def evaluate_obligations(cfg, now):
    """The `obligations` block of the digest. Pure with respect to the out-dir (reads the state file, writes nothing; run_once commits
    the state after the digest is written). Status per obligation: discharged (artefact predicate holds), else due (trigger holds),
    else pending (no trigger declared: pending forever, never escalates), or invalid (reason). A file that cannot be read is a file
    error, shown prominently; it never raises."""
    files = list(cfg.obligations) if cfg.obligations else [os.path.join(os.path.abspath(r), OBL_FILE) for r in cfg.root]
    found = [f for f in files if os.path.isfile(f)]
    out = {"files": [], "declared": 0, "counts": {"due": 0, "pending": 0, "discharged": 0, "invalid": 0}, "newly_discharged": 0,
           "items": [], "file_errors": 0, "searched": files, "escalation": "none"}
    state = load_obl_state(cfg)
    seen_ids = set()
    for fp in found:
        base = os.path.dirname(os.path.abspath(fp))
        ent = {"path": fp, "ok": True, "error": None, "n": 0}
        out["files"].append(ent)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if not isinstance(doc, dict) or doc.get("schema") != OBL_SCHEMA or not isinstance(doc.get("obligations"), list):
                raise ValueError('expected {"schema": %d, "obligations": [...]}' % OBL_SCHEMA)
        except (OSError, ValueError) as e:
            ent.update(ok=False, error=redact(" ".join(str(e).split()))[:140])
            out["file_errors"] += 1
            continue
        for i, o in enumerate(doc["obligations"][:OBL_MAX]):
            it = {"id": None, "title": None, "clause": None, "owner": None, "status": None, "reason": None, "file": fp, "escalation": "none",
                  "artifact": None, "trigger": None, "artifact_evidence": None, "trigger_evidence": None, "since_utc": None,
                  "newly_discharged": False}
            try:
                if not isinstance(o, dict):
                    raise ValueError("entry %d is not an object" % i)
                oid = o.get("id")
                it["id"] = oid if isinstance(oid, str) else "%s#%d" % (os.path.basename(fp), i)
                if not isinstance(oid, str) or not OBL_ID_RE.match(oid):
                    raise ValueError("id must match [A-Za-z0-9_.-]{1,64}")
                if oid in seen_ids:
                    raise ValueError("duplicate id")
                seen_ids.add(oid)
                for k in ("title", "clause", "owner"):
                    it[k] = o[k][:300] if isinstance(o.get(k), str) else None
                it["artifact"], it["trigger"] = o.get("artifact"), o.get("trigger")
                if "artifact" not in o:
                    raise ValueError("artifact is required: without it nothing can discharge the obligation")
                esc = o.get("escalation_when_due", "decide")
                if esc not in ("read", "decide"):
                    raise ValueError('escalation_when_due must be "read" or "decide"')
                done, it["artifact_evidence"] = eval_pred(o["artifact"], base, now)
                due, it["trigger_evidence"] = (eval_pred(o["trigger"], base, now) if o.get("trigger") is not None else (False, "no trigger declared"))
                it["status"] = "discharged" if done else "due" if due else "pending"
                if it["status"] == "due":
                    it["escalation"] = esc
            except ValueError as e:
                it["status"], it["escalation"] = "invalid", "read"
                it["reason"] = redact(" ".join(str(e).split()))[:160]
            st = state.get(it["id"], {}) if isinstance(state.get(it["id"]), dict) else {}
            if it["status"] == "due":
                it["since_utc"] = st.get("due_since_utc") or iso(now)
            elif it["status"] == "discharged":
                it["since_utc"] = st.get("discharged_utc") or iso(now)
                it["newly_discharged"] = not st.get("discharged_shown")
                out["newly_discharged"] += it["newly_discharged"]
            out["counts"][it["status"]] += 1
            ent["n"] += 1
            out["declared"] += 1
            out["items"].append(it)
    acts = {it["escalation"] for it in out["items"]}
    out["escalation"] = "decide" if "decide" in acts else "read" if ("read" in acts or out["file_errors"]) else "none"
    return out


def commit_obligation_state(cfg, obl, now):
    """After the digest is written: remember when each obligation first became due or discharged, and that a discharge has been shown
    once (so it then drops to a count). An obligation whose status moves back (artefact removed) forgets the discharge. Non-fatal."""
    if not obl or obl["file_errors"] and not obl["items"]:
        return
    old, new = load_obl_state(cfg), {}
    for it in obl["items"]:
        if it["id"] is None or it["status"] == "invalid":
            continue
        prev = old.get(it["id"], {}) if isinstance(old.get(it["id"]), dict) else {}
        if it["status"] == "due":
            new[it["id"]] = {"due_since_utc": it["since_utc"]}
        elif it["status"] == "discharged":
            new[it["id"]] = {"discharged_utc": it["since_utc"], "discharged_shown": True, "due_since_utc": prev.get("due_since_utc")}
    try:
        os.makedirs(cfg.out_dir, exist_ok=True)
        atomic_write(os.path.join(cfg.out_dir, OBL_STATE), json.dumps(new, indent=1) + "\n")
    except OSError:
        pass


def _obl_item_line(it):
    t = _clip(it["title"] or it["id"], 80)
    cl = " | clause: %s" % _clip(it["clause"], 90) if it["clause"] else ""
    if it["status"] == "invalid":
        return "- [read] INVALID obligation %s: %s (cannot be judged, so it may be invisible; fix %s)" % (
            it["id"], _clip(it["reason"], 120), os.path.basename(it["file"]))
    a = it["artifact"].get("path") if isinstance(it["artifact"], dict) else describe_pred(it["artifact"])
    if it["status"] == "due":
        return "- [%s] DUE %s: %s | artefact ABSENT: %s | triggered since %s by %s%s" % (
            it["escalation"], it["id"], t, _clip(a, 90), (it["since_utc"] or "?")[:16] + "Z", _clip(it["trigger_evidence"], 100), cl)
    if it["status"] == "pending":
        trig = "waiting for: " + _clip(describe_pred(it["trigger"]), 100) if it["trigger"] else "no trigger declared, never becomes due"
        return "- pending %s: %s | artefact absent: %s | %s%s" % (it["id"], t, _clip(a, 90), trig, cl)
    return "- discharged %s: %s | artefact present: %s | presence only, correctness not checked%s" % (
        it["id"], t, _clip(it["artifact_evidence"], 110), cl)


def obl_summary_lines(obl):
    """One line in the summary block, always: an empty or missing declaration must not read as 'nothing owed'."""
    if obl is None:
        return []
    c = obl["counts"]
    if not obl["files"] and not obl["file_errors"]:
        return ["Obligations: NONE DECLARED (no %s at %s): that is not the same as nothing owed" % (
            OBL_FILE, ", ".join(_clip(x, 60) for x in obl["searched"][:2]))]
    bits = []
    if c["due"]:
        bits.append("%d DUE" % c["due"])
    if c["invalid"]:
        bits.append("%d INVALID" % c["invalid"])
    bits.append("%d pending" % c["pending"])
    bits.append("%d discharged%s" % (c["discharged"], " (%d new, listed below)" % obl["newly_discharged"] if obl["newly_discharged"] else ""))
    line = "Obligations: %s of %d declared" % (", ".join(bits), obl["declared"])
    for f in obl["files"]:
        if not f["ok"]:
            line += " | FILE UNREADABLE %s: %s" % (_clip(f["path"], 70), _clip(f["error"], 90))
    return [line]


def obl_blocks(obl):
    """(priority, lines) pairs. Due and invalid obligations and unreadable files are priority 0, kept with the summary: a dropped
    obligation block reads as 'nothing owed'. Pending and newly discharged are priority 3, with the host-utilisation block."""
    if not obl:
        return []
    hot, cool = [], []
    for it in obl["items"]:
        (hot if it["status"] in ("due", "invalid") else cool if it["status"] == "pending" or it["newly_discharged"] else []).append(_obl_item_line(it))
    for f in obl["files"]:
        if not f["ok"]:
            hot.append("- [read] obligations file unreadable, nothing in it is being tracked: %s (%s)" % (_clip(f["path"], 80), _clip(f["error"], 100)))
    out = []
    if hot:
        out.append((0, "obligations due", hot[:OBL_SHOW] + (["- ... %d more due/invalid: see digest.json obligations.items" % (len(hot) - OBL_SHOW)] if len(hot) > OBL_SHOW else [])))
    if cool:
        out.append((3, "obligations pending", cool[:OBL_SHOW] + (["- ... %d more: see digest.json obligations.items" % (len(cool) - OBL_SHOW)] if len(cool) > OBL_SHOW else [])))
    return out


# ----------------------------------------------------------------------------- digest
def marker_set(d, cfg):
    """Names of terminal marker files present now: one stat each, no parsing."""
    return frozenset(m for m in cfg.markers if os.path.exists(os.path.join(d, m)))


def _expected_by_state(runs):
    """Audit of dispositioned runs: how many runs of each state carry expected=true (applied), so 11 stalls that were explained are
    visibly 11 explained stalls and not 11 stalls that stopped existing. Includes archived runs that were already escalation none."""
    out = {}
    for r in runs:
        if r["expected_applied"]:
            out[r["state"]] = out.get(r["state"], 0) + 1
    return out


def _inherited_sources(runs):
    """One entry per ancestor directory WHY file that dispositioned runs below it: who, where, how many runs, which states, and the
    run ids (at most 60), so 'N runs are fine' reads as 'N runs dispositioned by M files at these paths'."""
    by = {}
    for r in runs:
        ef = r.get("expected_from")
        if not ef or ef["kind"] != "inherited":
            continue
        e = by.setdefault(ef["id"], {"id": ef["id"], "dir": ef["dir"], "file": ef["file"], "note": (r["why"] or {}).get("note"),
                                     "applies_to_subtree": True, "runs": 0, "by_state": {}, "run_ids": []})
        e["runs"] += 1
        e["by_state"][r["state"]] = e["by_state"].get(r["state"], 0) + 1
        if len(e["run_ids"]) < 60:
            e["run_ids"].append(r["id"])
    return sorted(by.values(), key=lambda e: (-e["runs"], e["id"]))


CLUSTER_MAX = 100
CLUSTER_MAX_RUNS = 50


def cluster_signatures(runs):
    """Identical normalised signatures are ONE entry across runs: total count, number of runs, an exemplar, and one pointer per run
    (log, line range, count; at most CLUSTER_MAX_RUNS listed per cluster, the rest counted). Errors sort before warnings, then by
    the number of runs, then by count. Per-run signatures stay in each run's `errors`."""
    by = {}
    for r in runs:
        for s_ in r["errors"]["signatures"]:
            c = by.get(s_["signature"])
            ex = s_["exemplar"]
            if c is None:
                c = by[s_["signature"]] = {"signature": s_["signature"], "severity": s_["severity"], "count": 0, "n_runs": 0,
                                           "exemplar": ex["text"], "first_utc": None, "last_utc": None, "runs": [], "any_bad_run": False}
            c["count"] += s_["count"]
            c["n_runs"] += 1
            c["any_bad_run"] = c["any_bad_run"] or (r["state"] in ("failed", "stalled") and not r["expected_applied"])
            for k, f in (("first_utc", min), ("last_utc", max)):
                if s_[k]:
                    c[k] = s_[k] if c[k] is None else f(c[k], s_[k])
            if len(c["runs"]) < CLUSTER_MAX_RUNS:
                c["runs"].append({"id": r["id"], "state": r["state"], "count": s_["count"], "run_path": r["path"], "log": ex["log"],
                                  "line_start": ex["line_start"], "line_end": ex["line_end"]})
    out = sorted(by.values(), key=lambda c: (c["severity"] != "error", -c["n_runs"], -c["count"], c["signature"]))
    for c in out:
        c["runs_omitted"] = c["n_runs"] - len(c["runs"])
    return out[:CLUSTER_MAX]


def build_digest(cfg, states, now=None, sched=None):
    """sched (watch mode): run path -> {res, next}. A run is re-read only when its next-due time has arrived; otherwise its
    last result is reused (age refreshed). failed/stalled runs come due at the fast cadence whatever their tier. A terminal marker not seen at the last read makes
    its run due at once (one stat per marker name per tick)."""
    now = time.time() if now is None else now
    slack = 0.1 * cfg.interval if sched is not None else 0.0   # tick jitter must not push a due run one whole tick late
    runs, seen, queued = [], set(), []
    for r in discover(cfg, queued):
        seen.add(r["path"])
        ent = sched.get(r["path"]) if sched is not None else None
        if ent is not None and now + slack < ent["next"] and marker_set(r["path"], cfg) <= ent["markers"]:
            res = refresh_cached(dict(ent["res"]), r["path"], cfg, now)
        else:
            res = evaluate_run(r, cfg, states, now, None if sched is None else (ent["res"] if ent else {}))
            every = cfg.tiers["fast"]["recheck_s"] if res["state"] in ("failed", "stalled") else res["tier"]["recheck_s"]
            res["watch"] = {"last_eval_utc": iso(now), "next_eval_utc": iso(now + every), "recheck_s": every}
            if sched is not None:
                sched[r["path"]] = {"res": res, "next": now + every, "markers": marker_set(r["path"], cfg)}
        runs.append(res)
    if sched is not None:
        for k in [k for k in sched if k not in seen]:
            del sched[k]
    esc_rank = {"decide": 0, "read": 1, "none": 2}
    runs.sort(key=lambda r: (-STATE_RANK[r["state"]], esc_rank[r["escalation"]], r["id"]))
    counts = {k: 0 for k in STATE_RANK}
    for r in runs:
        counts[r["state"]] += 1
    worst = max((r["state"] for r in runs), key=lambda s: STATE_RANK[s]) if runs else "unknown"
    code = EXIT_CODES[worst] if runs else EXIT_NO_RUNS
    return {
        "generated_utc": iso(now), "host": socket.gethostname(), "roots": [os.path.abspath(r) for r in cfg.root],
        "tiers": cfg.tiers, "stall_override_s": cfg.stall_seconds, "watch_interval_s": cfg.interval if cfg.watch else None,
        "expected_downgrades": {"count": sum(1 for r in runs if r["escalation_before_expected"]),
                                "runs": [r["id"] for r in runs if r["escalation_before_expected"]],
                                "inherited_sources": _inherited_sources(runs)},
        "expected_by_state": _expected_by_state(runs),
        "signature_clusters": cluster_signatures(runs),
        "worst_state": worst if runs else "no_runs", "exit_code": code, "counts": counts, "queued": sorted(set(queued)),
        "obligations": evaluate_obligations(cfg, now), "runs": runs,
    }


def _clip(s, n):
    s = " ".join(str(s).replace("`", "'").split())
    return s if len(s) <= n else s[:max(0, n - 3)] + "..."


def _watch_cell(r):
    """Compact: tier/source last>next (UTC HH:MM), e.g. 'slow/file 14:20>15:20'."""
    w, t = r["watch"], r["tier"]
    return "%s/%s %s>%s" % ("med" if t["name"] == "medium" else t["name"], t["short"], w["last_eval_utc"][11:16], w["next_eval_utc"][11:16])


def _prog_cell(p):
    if not p or p.get("done") is None:
        return "-"
    s = "%d" % p["done"]
    if p.get("total"):
        s += "/%d %s" % (p["total"], ">100%" if p["done"] > p["total"] else "%.0f%%" % (p["percent"] or 0))
    else:
        s += " (total unknown)"
    if p.get("rate_per_min") is not None:
        s += " %g/min" % p["rate_per_min"]
    if p.get("eta_quality") == "suppressed":
        s += " no ETA"
    elif p.get("left_s"):
        s += " %s%s left" % ("rough " if p["eta_quality"] == "rough" else "", fmt_left(*p["left_s"]))
    return s


def _scope_lines(r, scope):
    sm = r["suspicious_metrics"]
    kinds = sm["by_scope"][scope]
    if not kinds:
        return []
    n = sum(kinds.values())
    out = ["- %s suspicious_metrics (%s scorer) %d: %s" % (
        r["id"], scope, n, ", ".join("%s x%d" % kv for kv in kinds.items()))]
    seen = set()
    for it in sm["items"]:
        if it["scope"] == scope and it["kind"] not in seen and len(seen) < 4:
            seen.add(it["kind"])
            out.append("  - %s %s = %s" % (it["kind"], _clip(it["path"], 100), it["value"]))
    return out


def _audit_lines(dg):
    """The disposition audit, in the always-kept summary block: counts per state, how many runs carry their own WHY file and how many
    inherited one from a directory file (applies_to_subtree), and each inheriting directory with its run count and note."""
    if not dg.get("expected_by_state"):
        return []
    inh = dg["expected_downgrades"]["inherited_sources"]
    n_inh = sum(e["runs"] for e in inh)
    n_all = sum(dg["expected_by_state"].values())
    out = ["Dispositioned by a WHY file with expected=true (escalation none, still counted above, flags kept in digest.json): %s | %d own, %d inherited by %d subtree file%s" % (
        ", ".join("%s %d" % kv for kv in sorted(dg["expected_by_state"].items())), n_all - n_inh, n_inh, len(inh), "" if len(inh) == 1 else "s")]
    for e in inh[:4]:
        out.append("  inherited: %s/%s (applies_to_subtree) covers %d runs (%s)%s" % (
            e["id"], e["file"], e["runs"], ", ".join("%s %d" % kv for kv in sorted(e["by_state"].items())),
            ": " + _clip(e["note"], 110) if e["note"] else ""))
    if len(inh) > 4:
        out.append("  inherited: +%d more subtree files, see digest.json expected_downgrades.inherited_sources" % (len(inh) - 4))
    return out


def build_blocks(dg, cfg):
    """Digest content as prioritised blocks: (priority, section, label, lines). Lower priority number survives longer.
    0 summary (with the NPU fragment and the dispositioned-by-WHY audit line) + status rows of unexplained failed/stalled/unknown runs;
    1 other status rows (including explained ones, expected=yes); 2 pointers and ERROR signatures of failed/stalled runs;
    3 flags on the primary scorer, then the host-utilisation (NPU) block; 4 ERROR signatures of other runs; 5 WARNING signatures and
    flags on other scorers; 6 everything else. Signatures are clustered across runs (one entry, count, runs, pointers)."""
    runs = dg["runs"]
    B = []

    def add(prio, section, label, lines):
        if lines:
            B.append((prio, section, label, lines))

    c = dg["counts"]
    add(0, "head", "summary", [
        "# Watchdog digest %s" % dg["generated_utc"],
        "worst=%s exit=%d | runs=%d: failed %d, stalled %d, unknown %d, running %d, done %d, archived %d | tick %s | host %s" % (
            dg["worst_state"], dg["exit_code"], len(runs), c["failed"], c["stalled"], c["unknown"], c["running"],
            c["done"], c["archived"], human_age(dg["watch_interval_s"]) if dg["watch_interval_s"] else "one-shot", dg["host"])
        + npu_fragment(dg.get("npu"))]
        + _audit_lines(dg) + obl_summary_lines(dg.get("obligations")))
    for prio, label, lines in obl_blocks(dg.get("obligations")):
        add(prio, "obl", label, lines)
    clean = [r for r in runs if r["state"] == "done" and r["escalation"] == "none"]
    arch = [r for r in runs if r["state"] == "archived"]
    shown = [r for r in runs if r not in clean and r not in arch]
    bad = ("failed", "stalled", "unknown")
    for r in shown:
        row = "| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            _clip(r["id"], 40), r.get("condition") or r["state"], r["escalation"] + (" expected=yes" if r["expected_applied"] else ""), human_age(r["age_s"]),
            _watch_cell(r), _clip(_prog_cell(r["progress"]), 48),
            _clip(_perf_cell(r.get("perf")) if r["state"] in ("running", "stalled") else "-", 64),
            _clip(r["escalation_reason"] or r["state_reason"], 70))
        # An explained stop (own WHY file or inherited from a directory) never outranks an unexplained run for space: its rows come
        # last; the audit lines in the summary block carry the counts, the files and their paths whether or not the rows fit.
        prio = 5 if r["expected_applied"] else 0 if r["state"] in bad else 1
        add(prio, "runs", "status rows", [row])
        if r["why"] and not r["why"].get("inherited_from"):
            add(prio, "runs", "explanatory notes",
                ["  note %s (%s): %s" % (r["id"], r["why"]["file"], _clip(r["why"]["note"], 110))])
    if not shown:
        add(0, "runs", "status rows", ["(no runs needing attention)"])
    if clean:
        add(6, "runs", "clean-done line", ["Clean done: %d (%s)" % (len(clean), _clip(
            ", ".join(r["id"] for r in clean[:6]) + (", ..." if len(clean) > 6 else ""), 120))])
    for r in arch:
        w = " - %s" % _clip(r["why"]["note"], 100) if r["why"] else ""
        add(6, "runs", "archived runs", ["Archived %s (idle %s, not escalated%s)%s" % (
            r["id"], human_age(r["age_s"]), ", expected=yes" if r["expected_applied"] else "", w)])

    for r in runs:
        rid_bad = r["state"] in ("failed", "stalled")
        sm = r["suspicious_metrics"]
        add(3, "flags", "flags on primary scorer", _scope_lines(r, "primary"))
        add(5, "flags", "flags on other scorers", _scope_lines(r, "other"))
        sp = sm["suppressed"]
        if sp["total"]:
            add(6, "flags", "suppression audit", ["- %s suppressed %d expected-degenerate values (%s); --no-suppress shows them" % (
                r["id"], sp["total"], ", ".join("%s x%d" % kv for kv in sp["by_role"].items()))])
        for n in r["notes"]:
            add(6, "flags", "run notes", ["- %s note: %s" % (r["id"], _clip(n, 120))])
        if r["escalation"] != "none":
            lines = ["- %s [%s] dir=%s" % (r["id"], r["escalation"], r["path"])]
            for p in r["pointers"][:3]:
                rel = p["path"][len(r["path"]) + 1:] if p["path"].startswith(r["path"] + "/") else p["path"]
                if "json_paths" in p:
                    lines.append("  - %s %s (%s)" % (rel, _clip(p["json_paths"][0], 70), p["why"]))
                else:
                    lines.append("  - %s:%d-%d (%s)" % (rel, p["line_start"], p["line_end"], p["why"]))
            prio = 2 if rid_bad else 3 if sm["by_scope"]["primary"] else 4 if r["errors"]["signatures"] else 6
            add(prio, "esc", "escalation pointers", lines)
    for c in dg.get("signature_clusters", []):
        err = c["severity"] == "error"
        lines = ["- %s x%d in %d run%s %s \"%s\"" % (
            "ERR" if err else "WARN", c["count"], c["n_runs"], "" if c["n_runs"] == 1 else "s",
            "%s..%s" % ((c["first_utc"] or "?")[5:19], (c["last_utc"] or "?")[5:19]) if c["first_utc"] or c["last_utc"] else "",
            _clip(c["exemplar"], cfg.exemplar_width))]
        ptr = []
        for x in c["runs"][:3]:
            rel = x["log"][len(x["run_path"]) + 1:] if x["log"].startswith(x["run_path"] + "/") else x["log"]
            ptr.append("%s@%s:%d-%d" % (_clip(x["id"], 44), rel, x["line_start"], x["line_end"]))
        more = c["n_runs"] - len(ptr)
        lines.append("  - %s%s" % ("; ".join(ptr), " (+%d more runs: pointers in digest.json signature_clusters)" % more if more > 0 else ""))
        add(2 if err and c["any_bad_run"] else 4 if err else 5, "errors", "error signatures" if err else "warning signatures", lines)
    if dg.get("npu"):
        # Chip state ranks right after the status rows, the failure pointers and the failed runs' own errors (priority 2) and the
        # primary-scorer flags, and above the error signatures of ordinary runs and every warning (a benign CANN warning that
        # appears in every run is the lowest-value line in the digest). One block (escalation lines + per-chip table), about 1 KB.
        add(3, "host", "host utilisation", npu_block_lines(dg["npu"], 2))
    return B


SECTIONS = [("head", []),
            ("obl", ["", "## Obligations (declared in obligations.json; status = does the artefact exist, NOT whether it is correct)"]),
            ("host", ["", "## Host utilisation (NPU: claimed = a resident process; AICore = latest snapshot [earlier passes]; claimed by = run named in the process command line)"]),
            ("runs", ["", "## Runs (worst first)", "| run | state | esc | age | watch | progress | perf | why |", "|---|---|---|---|---|---|---|---|",
                                      "(watch = tier/source last>next full read, UTC; file = WATCH.json, hbNm = inferred period, dflt = default. progress = SUM of the heartbeat row counters of all scorers, rate = change over the last 15 min of heartbeats; 'left' only with a declared total: a widened range assuming UNIFORM cost per row, wrong when work per row varies; 'no ETA' = run declared uniform_cost false; 'rough' = under 15 min seen. perf (running/stalled): per chip, xN chips, r= vs declared baseline, base? = none; host = CPU run)"]),
            ("flags", ["", "## Flags"]),
            ("esc", ["", "## Escalation (read: tier-1 reads these slices, paths relative to dir; decide: orchestrator chooses)"]),
            ("errors", ["", "## Signatures, clustered across runs (count, runs, first..last, exemplar, pointers)"])]
TAIL = ["", "Detail: digest.json beside this file."]
NOTE_RESERVE = 520


def _size(lines):
    return sum(len(x.encode("utf-8")) + 1 for x in lines)


def _assemble(blocks, keep):
    out = []
    for sec, head in SECTIONS:
        mine = [b for i, b in enumerate(blocks) if i in keep and b[1] == sec]
        if not mine:
            continue
        out.extend(head)
        for b in mine:
            out.extend(b[3])
    return out


def _render_blocks(blocks, cap):
    """Priority-ordered truncation: keep the lowest priority numbers;
    once a block of some priority does not fit, every block of a higher number is dropped too, so what survives is what matters."""
    full = _assemble(blocks, set(range(len(blocks)))) + TAIL
    if _size(full) <= cap:
        return "\n".join(full) + "\n"
    order = sorted(range(len(blocks)), key=lambda i: (blocks[i][0], i))
    keep, dropped, cut = set(), [], None
    budget = cap - NOTE_RESERVE
    for n, i in enumerate(order):
        b = blocks[i]
        if cut is not None and b[0] > cut:
            dropped.append(i)
            continue
        trial = keep | {i}
        if n == 0 or _size(_assemble(blocks, trial) + TAIL) <= budget:
            keep = trial
        else:
            dropped.append(i)
            cut = b[0] if cut is None else cut
    agg = {}
    for i in dropped:
        lab = blocks[i][2]
        cnt, byt = agg.get(lab, (0, 0))
        agg[lab] = (cnt + 1, byt + _size(blocks[i][3]))
    parts = ["%s x%d (%d B)" % (k, v[0], v[1]) for k, v in sorted(agg.items(), key=lambda kv: -kv[1][1])]
    note = "[TRUNCATED to %d bytes: dropped %d blocks, %d B: %s; priority order kept summary, failed/stalled, primary flags, errors; full detail in digest.json]" % (
        cap, len(dropped), sum(v[1] for v in agg.values()), "; ".join(parts))
    if len(note.encode()) > NOTE_RESERVE - 10:
        note = note.encode()[:NOTE_RESERVE - 20].decode("utf-8", "ignore") + "...]"
    text = "\n".join(_assemble(blocks, keep) + TAIL + [note]) + "\n"
    return enforce_cap(text, cap)


def render_md(dg, cfg):
    """digest.md: priority-ordered truncation of the blocks from build_blocks (see there for the order)."""
    return _render_blocks(build_blocks(dg, cfg), cfg.max_md_bytes)


def enforce_cap(text, cap):
    """Last-resort hard cut at a line boundary (the priority logic normally keeps the text under the cap already)."""
    if len(text.encode("utf-8")) <= cap:
        return text
    lines = text.split("\n")
    total = len(lines)
    note = "[TRUNCATED: digest.md exceeded %d bytes; %s lines dropped; full detail in digest.json]"
    kept = list(lines)
    while kept:
        cand = "\n".join(kept).rstrip("\n") + "\n" + note % (cap, total - len(kept)) + "\n"
        if len(cand.encode("utf-8")) <= cap:
            return cand
        kept.pop()
    return (note % (cap, total))[:cap] + "\n"


def write_outputs(dg, md, cfg):
    os.makedirs(cfg.out_dir, exist_ok=True)
    lockf = None
    try:
        lockf = open(os.path.join(cfg.out_dir, ".write.lock"), "a")
        fcntl.flock(lockf, fcntl.LOCK_EX)   # serialises writers so json and md always come from one pass
    except OSError:
        lockf = None
    try:
        atomic_write(os.path.join(cfg.out_dir, "digest.json"), json.dumps(dg, indent=1, sort_keys=False) + "\n")
        atomic_write(os.path.join(cfg.out_dir, "digest.md"), md)
    finally:
        if lockf:
            lockf.close()


NPU_HIST_KEY = "\0npu_hist"


def npu_pass(cfg, dg, states):
    """The `npu` block for this pass. Optional and non-fatal: any failure becomes an `available: false` block with the reason."""
    try:
        if NPU_HIST_KEY not in states:
            states[NPU_HIST_KEY] = load_npu_history(cfg)      # survives restarts and serves one-shot passes against the same out-dir
        hist = states[NPU_HIST_KEY]
        npu = analyse_npu(probe_npu(cfg), dg["runs"], dg["queued"], cfg, hist)
        if npu["available"]:
            save_npu_history(cfg, hist)
        return npu
    except Exception as e:   # noqa: BLE001 - the digest must survive a broken probe
        return {"available": False, "reason": "npu analysis failed: %s" % repr(e)[:100], "host": cfg.npu_host, "chips": [],
                "low": [], "no_process": [], "unknown": [], "owned_idle": [], "owned_idle_long": [], "free_unused": [], "ownership_unknown": [], "allocation": None,
                "wedged": [], "quiet": [], "flags": [], "escalation": "none", "sampled_utc": None, "samples": 0,
                "running_runs": 0, "queued_runs": 0}


def run_once(cfg, states, now=None, sched=None, npu=False):
    dg = build_digest(cfg, states, now, sched)
    if npu and not cfg.no_npu and cfg.npu_host:
        dg["npu"] = npu_pass(cfg, dg, states)
    md = render_md(dg, cfg)
    try:
        dg["retention_status"] = retain_pass(cfg, dg, md, time.time() if now is None else now)
    except Exception as e:   # noqa: BLE001 - retention must never break the digest
        dg["retention_status"] = {"enabled": True, "error": repr(e)[:120], "retained": None}
    write_outputs(dg, md, cfg)
    try:
        commit_obligation_state(cfg, dg.get("obligations"), time.time() if now is None else now)
    except Exception:   # noqa: BLE001
        pass
    return dg, md


def summary_line(dg):
    c = dg["counts"]
    return "%s worst=%s exit=%d runs=%d failed=%d stalled=%d unknown=%d running=%d done=%d" % (
        dg["generated_utc"], dg["worst_state"], dg["exit_code"], len(dg["runs"]), c["failed"], c["stalled"],
        c["unknown"], c["running"], c["done"])


def main(argv=None):
    cfg = make_cfg(**vars(build_parser().parse_args(argv)))
    states = {}
    if cfg.watch and cfg.interval < MIN_INTERVAL and not cfg.allow_fast_poll:
        print("error: --interval %g is below the %d s floor. Polling faster than 10 minutes spends I/O and attention on "
              "runs that cannot have changed; per-run cadence is set by tier (WATCH.json), not by a faster tick. "
              "Pass --allow-fast-poll to override (tests, debugging)." % (cfg.interval, MIN_INTERVAL), file=sys.stderr)
        return 2
    if not cfg.watch:
        dg, md = run_once(cfg, states, npu=True)
        print(summary_line(dg))
        if cfg.print_md:
            sys.stdout.write(md)
        return dg["exit_code"]
    # --watch: one instance per out-dir
    os.makedirs(cfg.out_dir, exist_ok=True)
    inst = open(os.path.join(cfg.out_dir, ".watch.lock"), "a")
    try:
        fcntl.flock(inst, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        if e.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
            print("another watchdog already watches %s; exiting" % cfg.out_dir, file=sys.stderr)
            return 3
    stop = []
    for sg in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sg, lambda *_: stop.append(1))
    code = 0
    sched = {}
    while not stop:
        t0 = time.time()
        try:
            dg, _ = run_once(cfg, states, sched=sched, npu=True)
            code = dg["exit_code"]
            print(summary_line(dg), flush=True)
        except Exception as e:   # a bad pass must not kill the watcher
            print("%s watchdog pass failed: %r" % (iso(time.time()), e), file=sys.stderr, flush=True)
        while not stop and time.time() - t0 < cfg.interval:
            time.sleep(min(1.0, max(0.05, cfg.interval - (time.time() - t0))))
    return code


if __name__ == "__main__":
    sys.exit(main())
