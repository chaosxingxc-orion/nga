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
STATE_RANK = {"done": 0, "running": 1, "unknown": 2, "stalled": 3, "failed": 4}
EXIT_CODES = {"done": 0, "running": 10, "unknown": 20, "stalled": 30, "failed": 40}
EXIT_NO_RUNS = 20
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
    a("--stall-seconds", type=float, default=300.0, help="heartbeat older than this, no marker => stalled (default 300)")
    a("--clock-skew-seconds", type=float, default=120.0, help="heartbeat further in the future than this => unknown")
    a("--window-seconds", type=float, default=900.0, help="throughput window (default 900)")
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
    a("--max-md-bytes", type=int, default=6000, help="hard cap on digest.md size in bytes (default 6000)")
    a("--min-n", type=int, default=30, help="cells with a sample count below this are flagged (default 30)")
    a("--min-cells", type=int, default=3, help="a table needs at least this many cells for the identical-metric check")
    a("--max-flags-per-kind", type=int, default=5, help="suspicious items listed per run and kind")
    a("--rate-keys", default=r"(?i)(?:^|[^a-z])(rate|acc|prec|recall|f1|auc|agree|consist|flip|score|readout|overall|share|constant|growth|ece)",
      help="regex marking a JSON key (leaf or up to 2 ancestors) as a rate/accuracy-like metric")
    a("--count-keys", default=r"^(n|n_units|n_items|n_samples|n_rows|count|samples|num_samples)$",
      help="regex for sample-count keys")
    a("--watch", action="store_true", help="loop forever, rewriting the digest in place")
    a("--interval", type=float, default=60.0, help="seconds between passes with --watch (default 60)")
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
    cfg.skip = set(x for x in cfg.skip_dirs.split(",") if x)
    cfg.ignore_re = re.compile(cfg.ignore) if cfg.ignore else None
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
        counters = {k: int(v) for k, v in _PAIR.findall(tail)}
        if counters:
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


def check_report(obj, cfg):
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
            items.append({"kind": "non_finite", "path": jpath(parts), "value": str(v), "detail": "NaN or infinite value"})
            continue
        if _is_count_key(parts, cfg) or v not in (0, 1):
            continue
        if isinstance(v, int) and not _rate_ctx(parts, cfg, leaf_only=True):
            continue
        if _rate_ctx(parts, cfg):
            items.append({"kind": "exact_zero" if v == 0 else "exact_one", "path": jpath(parts), "value": v,
                          "detail": "rate/accuracy exactly %s" % ("0.0" if v == 0 else "1.0")})
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
                                  "detail": "all %d cells equal; input may never have varied" % len(ch)})
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
                          "value": fv[0], "detail": "same value in all %d cells; input may never have varied" % len(ch)})

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
                                  "detail": "n=%s below minimum %d" % (v, cfg.min_n)})

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


def group_flags(items, cfg):
    by = {}
    for it in items:
        by.setdefault(it["kind"], []).append(it)
    out = {"total": len(items), "by_kind": {}, "items": [], "omitted": 0}
    for kind in sorted(by):
        lst = by[kind]
        out["by_kind"][kind] = len(lst)
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


def classify(marker, problem, hb_ts, hb_src, has_logs, now, cfg):
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
    age = now - hb_ts
    if age < -cfg.clock_skew_seconds:
        return "unknown", "heartbeat %ds in the future (clock skew between hosts?)" % int(-age)
    if age <= cfg.stall_seconds:
        return "running", "heartbeat %s ago via %s" % (human_age(age), hb_src)
    return "stalled", "heartbeat %s old (> %ds) via %s, no marker" % (human_age(age), int(cfg.stall_seconds), hb_src)


def escalate(state, flags_total, sigs):
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


def evaluate_run(run, cfg, states, now):
    d = run["path"]
    notes = []
    marker, problem = read_marker(d, cfg)
    logs = run_logs(d, cfg)
    hbp = os.path.join(d, cfg.heartbeat_name)
    samples, hb_ts, hb_src = [], None, None
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
    state, reason = classify(marker, problem, hb_ts, hb_src, bool(logs), now, cfg)
    if marker and hb_ts and marker["exit_code"] is not None and hb_ts > marker["ts"] + cfg.stall_seconds:
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
    sus = {"total": 0, "by_kind": {}, "items": [], "omitted": 0, "report": None}
    if os.path.isfile(rp):
        items, err = scan_report(rp, cfg)
        sus = group_flags(items, cfg)
        sus["report"] = rp
        if err:
            notes.append(err)

    esc, why = escalate(state, sus["total"], out_sigs)
    pointers = []
    if esc != "none":
        if state in ("failed", "stalled", "unknown") and newest is not None:
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
    progress = summarize_progress(samples, d, cfg) if samples else None
    if progress is None and state in ("running", "stalled"):
        progress = {"done": None, "total": None, "percent": None, "rate_per_min": None, "window_s": None,
                    "eta_utc": None, "note": "no heartbeat samples", "counters": None, "fields": None}
    return {
        "id": run["id"], "path": d, "state": state, "state_reason": reason, "escalation": esc, "escalation_reason": why,
        "heartbeat_utc": iso(hb_ts), "heartbeat_source": hb_src, "age_s": int(now - hb_ts) if hb_ts is not None else None,
        "marker": ({k: marker[k] for k in ("name", "path", "exit_code", "utc")} if marker else None),
        "progress": progress, "errors": errors, "suspicious_metrics": sus, "pointers": pointers[:6], "notes": notes,
        "logs": logs,
    }


# ----------------------------------------------------------------------------- digest
def build_digest(cfg, states, now=None):
    now = time.time() if now is None else now
    runs = [evaluate_run(r, cfg, states, now) for r in discover(cfg)]
    esc_rank = {"decide": 0, "read": 1, "none": 2}
    runs.sort(key=lambda r: (-STATE_RANK[r["state"]], esc_rank[r["escalation"]], r["id"]))
    counts = {k: 0 for k in STATE_RANK}
    for r in runs:
        counts[r["state"]] += 1
    worst = max((r["state"] for r in runs), key=lambda s: STATE_RANK[s]) if runs else "unknown"
    code = EXIT_CODES[worst] if runs else EXIT_NO_RUNS
    return {
        "generated_utc": iso(now), "host": socket.gethostname(), "roots": [os.path.abspath(r) for r in cfg.root],
        "stall_seconds": cfg.stall_seconds, "watch_interval_s": cfg.interval if cfg.watch else None,
        "worst_state": worst if runs else "no_runs", "exit_code": code, "counts": counts, "runs": runs,
    }


def _clip(s, n):
    s = " ".join(str(s).replace("`", "'").split())
    return s if len(s) <= n else s[:max(0, n - 3)] + "..."


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


def render_md(dg, cfg):
    L = []
    c = dg["counts"]
    L.append("# Watchdog digest %s" % dg["generated_utc"])
    L.append("worst=%s exit=%d | runs=%d: failed %d, stalled %d, unknown %d, running %d, done %d | stall>%ds | host %s" % (
        dg["worst_state"], dg["exit_code"], len(dg["runs"]), c["failed"], c["stalled"], c["unknown"], c["running"],
        c["done"], int(dg["stall_seconds"]), dg["host"]))
    runs = dg["runs"]
    clean = [r for r in runs if r["state"] == "done" and r["escalation"] == "none"]
    shown = [r for r in runs if r not in clean]
    L.append("")
    L.append("## Runs (worst first)")
    if shown:
        L.append("| run | state | esc | age | progress | why |")
        L.append("|---|---|---|---|---|---|")
        for r in shown:
            L.append("| %s | %s | %s | %s | %s | %s |" % (
                _clip(r["id"], 40), r["state"], r["escalation"], human_age(r["age_s"]), _clip(_prog_cell(r["progress"]), 48),
                _clip(r["escalation_reason"] or r["state_reason"], 70)))
    else:
        L.append("(no runs needing attention)")
    if clean:
        L.append("Clean done: %d (%s)" % (len(clean), _clip(", ".join(r["id"] for r in clean[:6]) + (", ..." if len(clean) > 6 else ""), 120)))

    flagged = [r for r in runs if r["suspicious_metrics"]["total"] or r["notes"]]
    L.append("")
    L.append("## Flags")
    if not flagged:
        L.append("none")
    for r in flagged:
        sm = r["suspicious_metrics"]
        if sm["total"]:
            kinds = ", ".join("%s x%d" % (k, v) for k, v in sm["by_kind"].items())
            L.append("- %s suspicious_metrics %d: %s" % (r["id"], sm["total"], kinds))
            seen = set()
            for it in sm["items"]:
                if it["kind"] not in seen and len(seen) < 4:
                    seen.add(it["kind"])
                    L.append("  - %s %s = %s" % (it["kind"], _clip(it["path"], 100), it["value"]))
        for n in r["notes"]:
            L.append("- %s note: %s" % (r["id"], _clip(n, 120)))

    esc = [r for r in runs if r["escalation"] != "none"]
    L.append("")
    L.append("## Escalation (read: tier-1 reads these slices, paths relative to dir; decide: orchestrator chooses)")
    if not esc:
        L.append("none")
    for r in esc:
        L.append("- %s [%s] dir=%s" % (r["id"], r["escalation"], r["path"]))
        for p in r["pointers"][:3]:
            rel = p["path"][len(r["path"]) + 1:] if p["path"].startswith(r["path"] + "/") else p["path"]
            if "json_paths" in p:
                L.append("  - %s %s (%s)" % (rel, _clip(p["json_paths"][0], 70), p["why"]))
            else:
                L.append("  - %s:%d-%d (%s)" % (rel, p["line_start"], p["line_end"], p["why"]))

    L.append("")
    L.append("## Error signatures (count, first..last, exemplar pointer)")
    any_sig = False
    for r in runs:
        e = r["errors"]
        if not e["signatures"]:
            continue
        any_sig = True
        L.append("- %s: %d error lines, %d warning lines, %d signatures" % (
            r["id"], e["error_lines"], e["warning_lines"], e["distinct_signatures"]))
        for s in e["signatures"]:
            ex = s["exemplar"]
            when = "%s..%s" % ((s["first_utc"] or "?")[5:19], (s["last_utc"] or "?")[5:19]) if s["first_utc"] or s["last_utc"] else "L%d..L%d" % (s["exemplar"]["line"], s["last_line"])
            lg = ex["log"][len(r["path"]) + 1:] if ex["log"].startswith(r["path"] + "/") else ex["log"]
            L.append("  - %s x%d %s @%s:%d-%d \"%s\"" % ("ERR" if s["severity"] == "error" else "WARN", s["count"], when, lg, ex["line_start"],
                                                         ex["line_end"], _clip(ex["text"], cfg.exemplar_width)))
        if e["omitted_signatures"]:
            L.append("  - ... %d more signatures omitted (%d occurrences)" % (e["omitted_signatures"], e["omitted_occurrences"]))
    if not any_sig:
        L.append("none")
    L.append("")
    L.append("Detail: digest.json beside this file.")
    text = "\n".join(L) + "\n"
    return enforce_cap(text, cfg.max_md_bytes)


def enforce_cap(text, cap):
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


def run_once(cfg, states, now=None):
    dg = build_digest(cfg, states, now)
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
    while not stop:
        t0 = time.time()
        try:
            dg, _ = run_once(cfg, states)
            code = dg["exit_code"]
            print(summary_line(dg), flush=True)
        except Exception as e:   # a bad pass must not kill the watcher
            print("%s watchdog pass failed: %r" % (iso(time.time()), e), file=sys.stderr, flush=True)
        while not stop and time.time() - t0 < cfg.interval:
            time.sleep(min(1.0, max(0.05, cfg.interval - (time.time() - t0))))
    return code


if __name__ == "__main__":
    sys.exit(main())
