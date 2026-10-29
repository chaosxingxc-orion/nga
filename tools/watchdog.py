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
    a("--marker-names", default="DONE,FAILED,exit_code,EXIT_CODE", help="terminal marker file names")
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
    a("--max-md-bytes", type=int, default=12000, help="hard cap on digest.md size in bytes (default 12000); sections are dropped by priority")
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


def classify_line(seg, cfg):
    """'error' | 'warning' | None. A line that says 'warning' and carries no hard error word is a warning
    even if it also says 'failed' (e.g. 'UserWarning: Failed to create processor')."""
    if cfg.ignore_re is not None and cfg.ignore_re.search(seg):
        return None
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
    return {"ts": ts, "done": done, "total": total, "counters": counters, "fields": fields}


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


def summarize_progress(samples, rundir, cfg):
    """samples: parsed heartbeat samples in file order. Returns progress dict (never guesses a total)."""
    prog = {"done": None, "total": None, "percent": None, "rate_per_min": None, "window_s": None,
            "eta_utc": None, "note": None, "counters": None, "fields": None}
    withdone = [s for s in samples if s["done"] is not None]
    if not withdone:
        prog["note"] = "heartbeat has no progress count"
        return prog
    last = withdone[-1]
    prog["done"] = last["done"]
    prog["counters"] = dict(list(last["counters"].items())[:6]) or None
    prog["fields"] = dict(list(last["fields"].items())[:6]) or None
    total = last["total"]
    src = "heartbeat" if total is not None else None
    if total is None:
        total, tf = read_total_file(rundir)
        src = tf
    prog["total"] = total
    if total:
        prog["percent"] = round(100.0 * min(last["done"], total) / total, 1)
    else:
        prog["note"] = "total unknown"
    # throughput: samples inside the window, after the last decrease of the counter (restart)
    start = 0
    for i in range(1, len(withdone)):
        if withdone[i]["done"] < withdone[i - 1]["done"]:
            start = i
    seg = [s for s in withdone[start:] if s["ts"] >= last["ts"] - cfg.window_seconds]
    if len(seg) >= 2 and seg[-1]["ts"] > seg[0]["ts"]:
        dt = seg[-1]["ts"] - seg[0]["ts"]
        rate = (seg[-1]["done"] - seg[0]["done"]) / dt
        prog["window_s"] = int(dt)
        prog["rate_per_min"] = round(rate * 60, 2)
        if total and rate > 0 and last["done"] < total:
            prog["eta_utc"] = iso(last["ts"] + (total - last["done"]) / rate)
        elif rate <= 0:
            prog["note"] = (prog["note"] + "; " if prog["note"] else "") + "no progress in window"
    else:
        prog["note"] = (prog["note"] + "; " if prog["note"] else "") + "too few heartbeats for a rate"
    return prog


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


def discover(cfg):
    runs, seen = [], set()
    roots = [os.path.abspath(r) for r in cfg.root]
    for root in roots:
        def walk(d, depth):
            real = os.path.realpath(d)
            if real in seen or real == cfg.out_dir:
                return
            ents = _entries(d)
            if is_run_dir(d, ents, depth, cfg):
                seen.add(real)
                rid = os.path.relpath(d, root) if d != root else os.path.basename(root)
                if len(roots) > 1:
                    rid = os.path.basename(root) + ":" + rid
                runs.append({"id": rid, "path": d})
                return
            if depth >= cfg.max_depth:
                return
            for n, isdir in sorted(ents):
                if isdir and not n.startswith((".", "_")) and n not in cfg.skip:
                    walk(os.path.join(d, n), depth + 1)
        if os.path.isdir(root):
            walk(root, 0)
    return runs


def read_marker(d, cfg):
    """Returns (marker_dict_or_None, problem_or_None)."""
    found = []
    for name in cfg.markers:
        p = os.path.join(d, name)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(2000)
            mtime = os.path.getmtime(p)
        except OSError:
            continue
        m = re.search(r"(?:\brc|exit(?:[_ ]?code)?)\s*[=:]\s*(-?\d+)", content, re.I)
        if m is None:
            m = re.match(r"\s*(-?\d+)\b", content)
        rc = int(m.group(1)) if m else None
        um = TS_RE.search(content)
        found.append({"name": name, "path": p, "exit_code": rc, "utc": iso(parse_ts(um)) if um and parse_ts(um) else iso(mtime),
                      "ts": parse_ts(um) if um and parse_ts(um) else mtime, "empty": not content.strip()})
    if not found:
        return None, None
    rcs = {m["exit_code"] for m in found if m["exit_code"] is not None}
    names = ",".join(m["name"] for m in found)
    mk = dict(found[0])
    if not rcs:
        return mk, "marker %s present but holds no parseable exit code" % names
    if len(rcs) > 1:
        return mk, "markers %s disagree on the exit code (%s)" % (names, sorted(rcs))
    rc = rcs.pop()
    mk["exit_code"] = rc
    if rc == 0 and any(m["name"].upper() == "FAILED" for m in found):
        return mk, "FAILED marker holds exit code 0"
    if rc != 0 and any(m["name"].upper() == "DONE" for m in found):
        return mk, "DONE marker holds non-zero exit code %d" % rc
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
    """(tier or None, error or None) from WATCH.json. Only the exact strings fast|medium|slow are accepted."""
    p = os.path.join(d, WATCH_FILE)
    if not os.path.isfile(p):
        return None, None
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, ValueError) as e:
        return None, "%s unreadable or not JSON: %s" % (p, str(e)[:60])
    if not isinstance(obj, dict):
        return None, "%s must hold a JSON object" % p
    if "tier" not in obj:
        return None, None
    t = obj["tier"]
    if not isinstance(t, str) or t not in TIER_NAMES:
        return None, "%s: invalid tier %s (expected exactly one of %s)" % (p, json.dumps(t)[:40], "|".join(TIER_NAMES))
    return t, None


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
    tier, err = read_watch_file(d)
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
        expected = False
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                expected = obj.get("expected") is True   # strictly the boolean true; never inferred from prose
                for k in ("note", "why", "reason", "summary", "cause", "message"):
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
        return {"file": name, "note": " ".join(note.split())[:300], "expected": expected}
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
    """Cheap per-tick refresh of a not-due run: only the heartbeat tail is re-read, so its progress, heartbeat time and age
    track the run. State, errors and report stay as of the last full read."""
    samples, hb_ts, hb_src, _ = read_heartbeat(d, cfg)
    if samples:
        res["progress"] = summarize_progress(samples, d, cfg)
        res["heartbeat_epoch"], res["heartbeat_utc"], res["heartbeat_source"] = hb_ts, iso(hb_ts), hb_src
        res["age_s"] = int(now - hb_ts)
    elif res.get("heartbeat_epoch") is not None:
        res["age_s"] = int(now - res["heartbeat_epoch"])
    return res


def evaluate_run(run, cfg, states, now, prev=None):
    """prev: None in a one-shot pass; in --watch the previous result for this run ({} on the first read)."""
    d = run["path"]
    notes = []
    marker, problem = read_marker(d, cfg)
    logs = run_logs(d, cfg)
    hbp = os.path.join(d, cfg.heartbeat_name)
    samples, hb_ts, hb_src, hb_notes = read_heartbeat(d, cfg)
    notes.extend(hb_notes)
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
    shards = shard_status(d, samples[-1]) if samples and state == "running" else None
    if shards and shards["note"] and shards["lost"]:
        notes.append("shards: " + shards["note"])
    pointers = []
    if esc != "none":
        if (state in ("failed", "stalled", "unknown") or flat_on) and newest is not None:
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
    why = read_why(d, cfg)
    esc_before, expected_applied = esc, False
    # "expected": true downgrades only a run with a terminal marker (done/failed) or an archived run. Running, stalled
    # and unknown runs keep their escalation whatever the file claims. A note alone never changes anything.
    if why and why["expected"] and (state == "archived" or (marker is not None and state in ("done", "failed"))):
        expected_applied = True
        if esc != "none":
            esc, why_text = "none", "expected=yes (was %s: %s)" % (esc_before, why_text)
    progress = summarize_progress(samples, d, cfg) if samples else None
    if progress is None and state in ("running", "stalled"):
        progress = {"done": None, "total": None, "percent": None, "rate_per_min": None, "window_s": None,
                    "eta_utc": None, "note": "no heartbeat samples", "counters": None, "fields": None}
    return {
        "id": run["id"], "path": d, "state": state, "state_reason": reason, "escalation": esc, "escalation_reason": why_text,
        "tier": {k: tier[k] for k in ("name", "short", "source", "recheck_s", "stall_s")},
        "heartbeat_epoch": hb_ts, "heartbeat_utc": iso(hb_ts), "heartbeat_source": hb_src, "age_s": int(now - hb_ts) if hb_ts is not None else None,
        "marker": ({k: marker[k] for k in ("name", "path", "exit_code", "utc")} if marker else None),
        "progress": progress, "errors": errors, "suspicious_metrics": sus, "pointers": pointers[:6], "notes": notes, "why": why,
        "progress_flat": flat_info, "flat_reads": flat_reads, "flat_done": flat_done, "shards": shards,
        "expected_applied": expected_applied, "escalation_before_expected": esc_before if esc_before != esc else None,
        "logs": logs,
    }


# ----------------------------------------------------------------------------- digest
def marker_set(d, cfg):
    """Names of terminal marker files present now: one stat each, no parsing."""
    return frozenset(m for m in cfg.markers if os.path.exists(os.path.join(d, m)))


def build_digest(cfg, states, now=None, sched=None):
    """sched (watch mode): run path -> {res, next}. A run is re-read only when its next-due time has arrived; otherwise its
    last result is reused (age refreshed). failed/stalled runs come due at the fast cadence whatever their tier. A terminal marker not seen at the last read makes
    its run due at once (one stat per marker name per tick)."""
    now = time.time() if now is None else now
    slack = 0.1 * cfg.interval if sched is not None else 0.0   # tick jitter must not push a due run one whole tick late
    runs, seen = [], set()
    for r in discover(cfg):
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
                                "runs": [r["id"] for r in runs if r["escalation_before_expected"]]},
        "worst_state": worst if runs else "no_runs", "exit_code": code, "counts": counts, "runs": runs,
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
        s += "/%d %.0f%%" % (p["total"], p["percent"] or 0)
    else:
        s += " (total unknown)"
    if p.get("rate_per_min") is not None:
        s += " %g/min" % p["rate_per_min"]
    if p.get("eta_utc"):
        s += " eta %s" % p["eta_utc"][5:16].replace("T", " ")
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


def build_blocks(dg, cfg):
    """Digest content as prioritised blocks: (priority, section, label, lines). Lower priority number survives longer.
    0 summary + status rows of failed/stalled/unknown; 1 other status rows; 2 failed/stalled runs (pointers, errors);
    3 flags on the primary scorer; 4 error signatures; 5 flags on other scorers; 6 everything else."""
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
            c["done"], c["archived"], human_age(dg["watch_interval_s"]) if dg["watch_interval_s"] else "one-shot", dg["host"])])
    clean = [r for r in runs if r["state"] == "done" and r["escalation"] == "none"]
    arch = [r for r in runs if r["state"] == "archived"]
    shown = [r for r in runs if r not in clean and r not in arch]
    bad = ("failed", "stalled", "unknown")
    for r in shown:
        row = "| %s | %s | %s | %s | %s | %s | %s |" % (
            _clip(r["id"], 40), r["state"], r["escalation"] + (" expected=yes" if r["expected_applied"] else ""), human_age(r["age_s"]),
            _watch_cell(r), _clip(_prog_cell(r["progress"]), 48),
            _clip(r["escalation_reason"] or r["state_reason"], 70))
        add(0 if r["state"] in bad else 1, "runs", "status rows", [row])
        if r["why"]:
            add(0 if r["state"] in bad else 1, "runs", "explanatory notes",
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
        e = r["errors"]
        if e["signatures"]:
            lines = ["- %s: %d error lines, %d warning lines, %d signatures" % (
                r["id"], e["error_lines"], e["warning_lines"], e["distinct_signatures"])]
            for s_ in e["signatures"]:
                ex = s_["exemplar"]
                when = ("%s..%s" % ((s_["first_utc"] or "?")[5:19], (s_["last_utc"] or "?")[5:19])
                        if s_["first_utc"] or s_["last_utc"] else "L%d..L%d" % (ex["line"], s_["last_line"]))
                lg = ex["log"][len(r["path"]) + 1:] if ex["log"].startswith(r["path"] + "/") else ex["log"]
                lines.append("  - %s x%d %s @%s:%d-%d \"%s\"" % ("ERR" if s_["severity"] == "error" else "WARN", s_["count"], when,
                                                                lg, ex["line_start"], ex["line_end"], _clip(ex["text"], cfg.exemplar_width)))
            if e["omitted_signatures"]:
                lines.append("  - ... %d more signatures omitted (%d occurrences)" % (e["omitted_signatures"], e["omitted_occurrences"]))
            add(2 if rid_bad else 4, "errors", "error signatures", lines)
    return B


SECTIONS = [("head", []), ("runs", ["", "## Runs (worst first)", "| run | state | esc | age | watch | progress | why |", "|---|---|---|---|---|---|---|",
                                      "(watch = tier/source last>next full read, UTC; file = WATCH.json, hbNm = inferred period, dflt = default. progress = SUM of the heartbeat row counters of all scorers, rate = change over the last 15 min of heartbeats)"]),
            ("flags", ["", "## Flags"]),
            ("esc", ["", "## Escalation (read: tier-1 reads these slices, paths relative to dir; decide: orchestrator chooses)"]),
            ("errors", ["", "## Error signatures (count, first..last, exemplar pointer)"])]
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


def render_md(dg, cfg):
    blocks = build_blocks(dg, cfg)
    cap = cfg.max_md_bytes
    full = _assemble(blocks, set(range(len(blocks)))) + TAIL
    if _size(full) <= cap:
        return "\n".join(full) + "\n"
    # Priority-ordered truncation: keep the lowest priority numbers; once a block of some priority does not fit,
    # every block of a higher number is dropped too, so what survives is what matters.
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


def run_once(cfg, states, now=None, sched=None):
    dg = build_digest(cfg, states, now, sched)
    md = render_md(dg, cfg)
    write_outputs(dg, md, cfg)
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
        dg, md = run_once(cfg, states)
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
            dg, _ = run_once(cfg, states, sched=sched)
            code = dg["exit_code"]
            print(summary_line(dg), flush=True)
        except Exception as e:   # a bad pass must not kill the watcher
            print("%s watchdog pass failed: %r" % (iso(time.time()), e), file=sys.stderr, flush=True)
        while not stop and time.time() - t0 < cfg.interval:
            time.sleep(min(1.0, max(0.05, cfg.interval - (time.time() - t0))))
    return code


if __name__ == "__main__":
    sys.exit(main())
