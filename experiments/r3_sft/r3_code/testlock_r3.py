"""Test lock (R3-SFT-PREREG sec 8.4).

    1. The final model is named in FINAL.json in the round directory.
    2. Only then is each test partition (clean and variants) read, once, by that model.
    3. Each read appends one line to TEST-READS.log: UTC time, model path and sha256, suite, partition, n and headline accuracy.

"The scorer refuses a test partition unless the model is named in FINAL.json and has no earlier line for that partition."
core_r3.load_partition is the only function that opens a Kev partition and it demands a TestTicket for `test`; the only
way to obtain a ticket is `authorize_test_read` below.

Model identity. The model of record of a tuned arm is an UNMERGED LoRA adapter on a base checkpoint, so its identity is
the sha256 over the adapter files plus the base revision (the first line of the base directory's `.complete`). An untuned or
fully fine-tuned checkpoint is identified by the sha256 over its weight files plus the revision. `path` in FINAL.json and in
TEST-READS.log is the adapter directory for an adapter, the model directory otherwise.

FINAL.json schema (the prereg names the file but not its layout; this is the reading):
    {"round": "...", "size": "0.8B", "named_utc": "...", "models": [{"label": "K1 seed 2", "path": "...", "sha256": "..."}, ...]}
TEST-READS.log is tab-separated, one line per read: utc, path, sha256, suite, partition, n, headline_accuracy.
"""
import fcntl
import json
import os

import core_r3 as C

FINAL_NAME = "FINAL.json"
LOG_NAME = "TEST-READS.log"            # the prereg's name (the earlier eval_r3.py wrote TEST_READS.log)
HASH_CACHE_NAME = ".model_hash_cache.json"
WEIGHT_SUFFIXES = (".safetensors", ".bin", ".pt")
ADAPTER_SUFFIXES = (".safetensors", ".bin", ".pt", ".json")


class TestTicket:
    """Proof that sec 8.4 steps 1 and 3 hold for exactly one (model, suite, partition). Created only by authorize_test_read."""
    __slots__ = ("identity", "suite", "split", "utc")

    def __init__(self, identity, suite, split, token):
        if token is not _TOKEN:
            raise TypeError("build a TestTicket with authorize_test_read")
        self.identity, self.suite, self.split, self.utc = identity, suite, split, C.utc_now()


_TOKEN = object()


def _abs(path):
    return os.path.abspath(os.path.normpath(path))


def _load_cache(round_dir):
    try:
        with open(os.path.join(round_dir, HASH_CACHE_NAME), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_cache(round_dir, cache):
    try:
        os.makedirs(round_dir, exist_ok=True)
        tmp = os.path.join(round_dir, HASH_CACHE_NAME + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, os.path.join(round_dir, HASH_CACHE_NAME))
    except OSError:
        pass   # the cache is an optimization only


def _file_hash(path, cache):
    st = os.stat(path)
    key = f"{_abs(path)}|{st.st_size}|{st.st_mtime_ns}"
    if key not in cache:
        cache[key] = C.sha256_file(path)
    return cache[key]


def base_revision(model_dir):
    """First line of the mirror's `.complete` (the pinned HF revision, prereg sec 2.1); 'unknown' if absent."""
    try:
        with open(os.path.join(model_dir, ".complete"), encoding="utf-8") as f:
            return f.readline().strip() or "unknown"
    except OSError:
        return "unknown"


def _files_under(root, suffixes):
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if not d.startswith("."))
        for f in sorted(fn):
            if f.startswith(".") or not f.endswith(suffixes):
                continue
            out.append(os.path.join(dp, f))
    return out


def model_identity(model_path, adapter=None, round_dir=C.ROUND_DIR):
    """-> {"path", "sha256", "kind", "base_path", "base_revision", "files": {relative path: sha256}}.

    adapter given: path = adapter dir, sha256 = H(adapter files, base revision, base path); the base weights are NOT hashed
    (the revision pins them). No adapter: sha256 = H(weight files, revision)."""
    cache = _load_cache(round_dir)
    rev = base_revision(model_path)
    if adapter:
        root = _abs(adapter)
        files = {os.path.relpath(p, root): _file_hash(p, cache) for p in _files_under(root, ADAPTER_SUFFIXES)}
        if not files:
            raise ValueError(f"adapter directory {adapter} holds no adapter files")
        payload = {"kind": "lora-adapter-unmerged", "adapter_files": files, "base_revision": rev, "base_path": _abs(model_path)}
        out = {"path": root, "kind": "lora-adapter-unmerged", "base_path": _abs(model_path), "base_revision": rev, "files": files}
    else:
        root = _abs(model_path)
        files = {os.path.relpath(p, root): _file_hash(p, cache) for p in _files_under(root, WEIGHT_SUFFIXES)}
        if not files:
            raise ValueError(f"model directory {model_path} holds no weight files")
        payload = {"kind": "checkpoint", "weight_files": files, "revision": rev}
        out = {"path": root, "kind": "checkpoint", "base_path": root, "base_revision": rev, "files": files}
    out["sha256"] = C.sha256_text(C.canonical_json(payload))
    _save_cache(round_dir, cache)
    return out


# ---- FINAL.json and TEST-READS.log ------------------------------------------------------------------------------------

def read_final(round_dir):
    path = os.path.join(round_dir, FINAL_NAME)
    if not os.path.exists(path):
        raise C.TestLockRefusal(f"sec 8.4: no {FINAL_NAME} in {round_dir}; test partitions stay locked")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    models = doc.get("models") if isinstance(doc, dict) else doc
    if not isinstance(models, list) or not models:
        raise C.TestLockRefusal(f"sec 8.4: {path} names no model")
    for m in models:
        if not (isinstance(m, dict) and isinstance(m.get("path"), str) and isinstance(m.get("sha256"), str)):
            raise C.TestLockRefusal(f"sec 8.4: malformed entry in {path}: {m!r}")
    return doc


def is_named(final_doc, identity):
    models = final_doc.get("models") if isinstance(final_doc, dict) else final_doc
    return any(_abs(m["path"]) == _abs(identity["path"]) and m["sha256"] == identity["sha256"] for m in models)


def read_log(round_dir):
    path = os.path.join(round_dir, LOG_NAME)
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) == 7:
                        rows.append(dict(zip(("utc", "path", "sha256", "suite", "partition", "n", "headline_accuracy"), parts)))
    return rows


def earlier_reads(round_dir, identity, suite, split):
    """Lines of TEST-READS.log by this model (same sha256) for this partition."""
    return [r for r in read_log(round_dir) if r["sha256"] == identity["sha256"] and r["suite"] == suite and r["partition"] == split]


def authorize_test_read(identity, suite, split, round_dir=C.ROUND_DIR):
    """sec 8.4: returns a TestTicket, or raises core_r3.TestLockRefusal."""
    if split != "test":
        raise ValueError("authorize_test_read is for the test partition only")
    final = read_final(round_dir)
    if not is_named(final, identity):
        raise C.TestLockRefusal(f"sec 8.4: model {identity['path']} (sha256 {identity['sha256'][:12]}...) is not named in "
                                f"{os.path.join(round_dir, FINAL_NAME)}")
    prior = earlier_reads(round_dir, identity, suite, split)
    if prior:
        raise C.TestLockRefusal(f"sec 8.4: {suite}/{split} was already read by this model at {prior[0]['utc']}")
    return TestTicket(identity, suite, split, _TOKEN)


def record_test_read(ticket, n, headline_accuracy, round_dir=C.ROUND_DIR):
    """Append the sec 8.4 line (under an exclusive lock, re-checking that no earlier line exists). Returns the line."""
    if not isinstance(ticket, TestTicket):
        raise C.TestLockRefusal("sec 8.4: a TestTicket is required to log a test read")
    os.makedirs(round_dir, exist_ok=True)
    path = os.path.join(round_dir, LOG_NAME)
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            if earlier_reads(round_dir, ticket.identity, ticket.suite, ticket.split):
                raise C.TestLockRefusal(f"sec 8.4: {ticket.suite}/{ticket.split} already has a line for this model")
            line = "\t".join([C.utc_now(), ticket.identity["path"], ticket.identity["sha256"], ticket.suite, ticket.split,
                              str(int(n)), "%.6f" % headline_accuracy])
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return line
