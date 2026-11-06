"""Shared primitives of the R3 round-1 evaluation harness (R3-SFT-PREREG.md; clause numbers cited as "sec n.m").

Pure Python (no torch, no numpy). Everything the other `*_r3.py` evaluation modules share lives here, so that they
can be imported without importing eval_r3.py (which is being edited by another engineer and pulls in the scorer).

Scorer interface used by every module of this harness (so that any scorer can be dropped in):

    score_fn(rows, input_mode="full") -> list of lists of floats

`rows` are converted-Kev rows or Track T records (dicts with `levels`, `input`, `question`, ...); `input_mode` is the
prompt.py input mode ("full" | "blank" | "drop"); the result has, per row, the RAW per-option scores s_i (sec 3.2: the
unnormalized sum of the label token log-probabilities, fp32), aligned with `row["levels"]`.
"""
import datetime
import hashlib
import json
import math
import os
import sys

R0_CODE = "/mnt/cephfs/xingchao/experiments/jev/r0_code"
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (R0_CODE, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

KEV_DIR = "/mnt/cephfs/xingchao/experiments/jev/KEV"
DATA_ROOT = "/mnt/cephfs/xingchao/experiments/jev"
ROUND_DIR = "/mnt/cephfs/xingchao/experiments/jev/r3_runs"
KEV_REPO = "/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev"
KEV_RAW_TRAIN = "/mnt/cephfs/xingchao/datasets/jev/jaredpalmer__kev-suites/v7/decision-v7/train.jsonl"

SUITES = ("decision-v7", "transfer-v4")
INPUT_MODES = ("full", "blank", "drop")
KEV_VARIANTS = ("permuted", "none_present", "none_absent")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ---- the decision rules on raw scores (sec 4.2) -----------------------------------------------------------------

def argmax_first(scores):
    """numpy.argmax convention: the FIRST maximal index in the stored option order wins (sec 4.2, KEV-PROTOCOL sec 4)."""
    best_i, best_v = 0, scores[0]
    for i, v in enumerate(scores):
        if v > best_v:
            best_i, best_v = i, v
    return best_i


def is_tie(scores):
    """Two or more options exactly equal at the top of the raw fp32 scores (sec 4.2)."""
    m = max(scores)
    return sum(1 for s in scores if s == m) >= 2


TAU_S = 1e-3                 # nats; the admissibility bar of R3 sec 14.6 item 3 (fp32 scores differ across layouts by <= 1.3e-4, measured)
CENSUS_LISTED_CAP = 50       # listed items stored per census; the count is always complete


def top2_gap(scores):
    """Gap between the largest and the second-largest raw score (0.0 for an exact tie at the top); None for a one-option question."""
    if len(scores) < 2:
        return None
    t = sorted(scores, reverse=True)
    return t[0] - t[1]


def near_tie_census(scores, gold=None, keys=None, option_ids=None, tau=TAU_S):
    """Near-tie census of one set of raw per-option score vectors (R3 sec 14.6 items 3-4): the questions whose argmax is decided by less
    than the layout noise, which is the number that tells a reader how far the headline can move without the model changing at all.

    Gold-free part: n, one-option questions (no gap), exact ties, questions with top-2 gap <= tau, <= 10 tau, <= 100 tau, the minimum gap,
    and the listed items at or below tau (key or index, gap, tie flag and, given `option_ids` (the level ids per question, aligned with the
    scores), the top-2 candidates as sec 14.9 item 5 requires; at most CENSUS_LISTED_CAP, `listed_truncated` says so).
    With `gold` (index of the gold option per question; None entries are skipped): the exposure of the Kev-rule headline, i.e. how many of
    the listed items are currently correct and how many would become correct if the near-tied runner-up won, and the accuracy interval
    that follows. The interval is a statement about the harness's resolution, never a confidence interval."""
    n = len(scores)
    gaps = [top2_gap(s) for s in scores]
    listed_idx = [i for i, g in enumerate(gaps) if g is not None and g <= tau]
    out = {"tau": tau, "n": n, "n_one_option": sum(1 for g in gaps if g is None),
           "exact_tie_count": sum(1 for s in scores if is_tie(s)),
           "n_gap_le_tau": len(listed_idx),
           "n_gap_le_10tau": sum(1 for g in gaps if g is not None and g <= 10 * tau),
           "n_gap_le_100tau": sum(1 for g in gaps if g is not None and g <= 100 * tau),
           "min_gap": min((g for g in gaps if g is not None), default=None)}
    listed = sorted(listed_idx, key=lambda i: (gaps[i], i))
    def top2(i):
        order = sorted(range(len(scores[i])), key=lambda j: (-scores[i][j], j))[:2]
        return [option_ids[i][j] for j in order] if option_ids is not None else order
    out["listed"] = [{"item": (keys[i] if keys is not None else i), "gap": gaps[i], "tie": is_tie(scores[i]), "top2": top2(i)} for i in listed[:CENSUS_LISTED_CAP]]
    out["listed_truncated"] = len(listed) > CENSUS_LISTED_CAP
    if gold is not None:
        scored = [i for i in range(n) if gold[i] is not None]
        correct = sum(1 for i in scored if argmax_first(scores[i]) == gold[i])
        lc = rc = 0
        for i in listed_idx:
            if gold[i] is None:
                continue
            pred = argmax_first(scores[i])
            if pred == gold[i]:
                lc += 1                                   # currently correct, could be lost
            else:
                order = sorted(range(len(scores[i])), key=lambda j: (-scores[i][j], j))
                if gold[i] in order[:2]:
                    rc += 1                               # gold is the near-tied runner-up (or tied behind the first index): could be gained
        m = len(scored)
        out["headline_exposure"] = {"n_with_gold": m, "correct_kev": correct, "listed_correct": lc, "listed_gold_is_runner_up": rc,
                                    "kev_accuracy": (correct / m) if m else None,
                                    "kev_accuracy_interval": [(correct - lc) / m, (correct + rc) / m] if m else None}
    return out


def duplicate_option_audit(rows):
    """String-level half of the duplicate-candidate vacuity audit (R3 sec 14.6 item 4, as corrected): questions of `rows` with two or
    more levels carrying the same scored option string (" " + level name under the record_name render). The rule that scores such
    candidates once is a declared-vacuous safeguard, and this count is what keeps that declaration honest: it must be 0 on every suite
    the round reads; a non-zero count is reported, not hidden, and the report says the safeguard was exercised."""
    dup = [r for r in rows if len({l["name"] for l in r["levels"]}) < len(r["levels"])]
    return {"n": len(rows), "questions_with_duplicate_option_string": len(dup),
            "vacuous": not dup, "examples": [kev_key(r) if "kev" in r else r.get("key") for r in dup[:5]]}


def softmax(scores):
    """Same function as the R0 scorer's (fsum normalizer)."""
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    z = math.fsum(exps)
    return [e / z for e in exps]


# ---- Kev rows -------------------------------------------------------------------------------------------------------

def level_ids(row):
    return [l["id"] for l in row["levels"]]


def gold_index(row):
    return level_ids(row).index(row["gold"])


def kev_key(row):
    """Identity of one converted-Kev question row (clean and variant rows alike): kev.id + '/' + qindex."""
    return f"{row['kev']['id']}/{row['kev']['qindex']}"


def parent_key(row):
    """Key of the clean parent of a variant row (kev.parent_id + kev.qindex), sec 2.2."""
    return f"{row['kev']['parent_id']}/{row['kev']['qindex']}"


def partition_path(suite, split, variants=False, kev_dir=KEV_DIR):
    return os.path.join(kev_dir, suite, f"{split}.variants.jsonl" if variants else f"{split}.jsonl")


class TestLockRefusal(RuntimeError):
    """A test partition was requested without a valid ticket (sec 8.4)."""


def read_jsonl(path, limit=0):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
                if limit and len(rows) >= limit:
                    break
    return rows


def load_partition(suite, split, variants=False, limit=0, ticket=None, kev_dir=KEV_DIR):
    """The ONLY function of the harness that opens a Kev partition file. A test partition is refused unless `ticket`
    is a testlock_r3.TestTicket issued for exactly this (suite, split) (sec 8.4: the scorer refuses any test
    partition unless the model is named in FINAL.json and has no earlier read of it)."""
    if split == "test":
        import testlock_r3 as _tl   # late import: testlock_r3 imports this module
        if not isinstance(ticket, _tl.TestTicket) or ticket.suite != suite or ticket.split != split:
            raise TestLockRefusal(f"sec 8.4: refusing to open {suite}/{split}: no valid test ticket")
    path = partition_path(suite, split, variants, kev_dir)
    if variants and not os.path.exists(path):
        return [], path
    return read_jsonl(path, limit), path


# ---- headline metric (sec 4.1, 4.2) ----------------------------------------------------------------------------------

def headline(rows, scores):
    """Kev-rule accuracy (headline), R0-rule accuracy (tie = not correct), tie count; per-source and per-level_type
    breakdowns beside it, never as a headline (sec 4.1). Every accuracy carries n and the tie count (sec 10.1)."""
    def new():
        return {"n": 0, "kev": 0, "r0": 0, "ties": 0}

    tot, by_src, by_type = new(), {}, {}
    for row, s in zip(rows, scores):
        gi = gold_index(row)
        pred = argmax_first(s)
        tie = is_tie(s)
        for b in (tot, by_src.setdefault(row["source"], new()), by_type.setdefault(row["level_type"], new())):
            b["n"] += 1
            b["kev"] += int(pred == gi)
            b["r0"] += int(pred == gi and not tie)
            b["ties"] += int(tie)

    def fin(b):
        n = b["n"]
        return {"n": n, "kev_rule_accuracy": b["kev"] / n if n else None, "r0_rule_accuracy": b["r0"] / n if n else None,
                "tie_count": b["ties"]}
    out = fin(tot)
    out["by_source"] = {k: fin(v) for k, v in sorted(by_src.items())}
    out["by_level_type"] = {k: fin(v) for k, v in sorted(by_type.items())}
    return out


def gold_position_distribution(rows):
    c = {}
    for r in rows:
        c[gold_index(r)] = c.get(gold_index(r), 0) + 1
    return {str(k): v for k, v in sorted(c.items())}


def readout_row(row, s, variant=None):
    """One stored Track K readout (sec 3.2, 12.6: the raw s_i are stored with the decision made from them)."""
    return {"k": kev_key(row), "variant": variant or row.get("variant", "original"), "source": row["source"],
            "level_type": row["level_type"], "qname": row["qname"], "ids": level_ids(row), "gold": row["gold"],
            "gold_index": gold_index(row), "s": list(s), "argmax": argmax_first(s), "tie": is_tie(s)}


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    os.replace(tmp, path)


class ReadoutStore:
    """Item-granular resumable readout file (CLAUDE.md sec 7: an interrupted run restarts where it stopped).

    The file is appended line by line; a truncated last line of a killed run is dropped on open. `get(key)` returns a
    stored object or None."""

    def __init__(self, path):
        self.path = path
        self.done = {}
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        good = 0
        if os.path.exists(path):
            with open(path, "rb") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        self.done[obj["k"]] = obj
                    except (ValueError, KeyError):
                        break
                    good += len(line)
            with open(path, "r+b") as f:
                f.truncate(good)
        self._fh = open(path, "a", encoding="utf-8")

    def append(self, obj):
        self._fh.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self._fh.flush()
        self.done[obj["k"]] = obj

    def close(self):
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def score_resumable(score_fn, rows, key_fn, make_obj, store, input_mode="full", chunk=32, progress=None):
    """Score `rows` with `score_fn`, skipping rows already in `store`; append `make_obj(row, s)` per scored row.
    Returns {key: stored object} for all rows. `progress(done, total)` is called after every chunk."""
    todo = [r for r in rows if key_fn(r) not in store.done]
    for i in range(0, len(todo), chunk):
        batch = todo[i:i + chunk]
        for r, s in zip(batch, score_fn(batch, input_mode)):
            store.append(make_obj(r, s))
        if progress:
            progress(len(rows) - len(todo) + min(i + chunk, len(todo)), len(rows))
    return {key_fn(r): store.done[key_fn(r)] for r in rows}


# ---- run directory layout (one evaluation run = one model) ---------------------------------------------------------------------

def k_dir(run_dir, suite, split):
    return os.path.join(run_dir, "trackk", f"{suite}__{split}")


def k_readout_path(run_dir, suite, split, kind="clean"):
    """kind: clean | variants | question_only | empty_input (stored raw-score readouts, Track K)."""
    return os.path.join(k_dir(run_dir, suite, split), f"{kind}.jsonl")


HARNESS_IDENTITY = "harness_identity"      # R3 sec 14.5 item 1: readouts of the padded R0 scorer live under r3_runs/harness_identity/


class HarnessIdentitySource(Exception):
    """A report of record names (or would read) a file under harness_identity/ (R3 sec 14.5 item 1)."""


def names_harness_identity(text):
    """True when a string names a path under (or equal to) a harness_identity/ directory."""
    if not isinstance(text, str):
        return False
    t = text.replace("\\", "/")
    return (HARNESS_IDENTITY + "/") in t or t.rstrip("/").endswith("/" + HARNESS_IDENTITY) or t == HARNESS_IDENTITY


def find_harness_identity_sources(obj, where="$"):
    """Every string in a nested report that names a harness_identity/ path, as (location, string)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += find_harness_identity_sources(v, f"{where}.{k}")
            if names_harness_identity(k):
                out.append((f"{where}.<key>", k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out += find_harness_identity_sources(v, f"{where}[{i}]")
    elif names_harness_identity(obj):
        out.append((where, obj))
    return out


def refuse_harness_identity(report_or_path, what="report of record"):
    """Raise HarnessIdentitySource if a path, or any string inside a report, names a file under harness_identity/. The padded-scorer
    readouts there are an R0 artifact (the erratum difference), never an input of a report of record of this round."""
    hits = [("path", report_or_path)] if isinstance(report_or_path, str) and names_harness_identity(report_or_path) else \
        ([] if isinstance(report_or_path, str) else find_harness_identity_sources(report_or_path))
    if hits:
        raise HarnessIdentitySource(f"R3 sec 14.5 item 1: a {what} may not name a source under {HARNESS_IDENTITY}/: {hits[:3]}")


def load_report(run_dir):
    refuse_harness_identity(run_dir, "report read")
    with open(os.path.join(run_dir, "report.json"), encoding="utf-8") as f:
        return json.load(f)
