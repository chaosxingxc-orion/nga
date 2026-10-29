"""Shared constants, record loading and key derivation for the R0 baseline harness.

The task files are untrusted input. They are parsed with ``json`` only, every record is validated
against the schema in ``experiments/README.md``, and nothing from them is ever executed.

Vocabulary follows CLAUDE.md section 4: input, level, readout, harness, defect N.
"""
import hashlib
import json
import os

# Variant names, fixed by the task builder (experiments/build_tasks.py).
T1_VARIANTS = ("original", "digits", "letters", "random")
T3_VARIANTS = ("prefix_1q", "prefix_3q", "prefix_5q", "prefix_5q_shuffled")
# Variant sets of the invariance tasks (flip rate is defined over all unordered pairs of these).
INVARIANCE_VARIANTS = {"T1": T1_VARIANTS, "T3": T3_VARIANTS}
FLOOR_VARIANT = {"T1": "original", "T2": "base", "T3": "prefix_1q"}  # accuracy-floor variant per task (pre-reg 3, item 1)
LEVEL_TYPES = ("boolean", "nominal", "ordinal")
TASKS = ("T1", "T2", "T3")

# Relative to the cephfs experiment root.
TASK_DIRS = {"T1": "T1_level_names", "T2": "T2_definition_swap",
             "T3": "T3_question_set"}
SOURCE_FILES = ("typed-decisions", "openjev-synth", "akhilaaa3")  # T3 exists for typed-decisions only

DEFAULT_DATA_ROOT = "/mnt/cephfs/xingchao/experiments/jev"
DEFAULT_OUT_ROOT = "/mnt/cephfs/xingchao/experiments/jev/r0_baseline"

REQUIRED_FIELDS = (
    "source", "group_id", "task", "qname", "input", "task_definition", "question",
    "levels", "level_type", "candidate_set", "variant", "gold",
)


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def levelset_version(levels):
    """Version of a level set as the model sees it: ordered (id, name, definition) triples."""
    return sha256_hex(canonical_json([[l["id"], l["name"], l["definition"]] for l in levels]))[:16]


def unit_key(rec):
    """One business situation: all variants of the same input, question and group share this key.

    A group_id can hold several situations (openjev-synth: two inputs per group; akhilaaa3: several
    questions per case), so the key also includes qname and the input text.
    """
    return sha256_hex(canonical_json([rec["source"], rec["group_id"], rec["qname"], rec["input"]]))[:16]


def item_key(rec):
    """Stable identity of one scored record; used for resume and for the mock scorer's seed."""
    return sha256_hex(canonical_json([
        rec["task"], rec["variant"], unit_key(rec), rec["question"], rec["task_definition"], rec.get("prefix_questions"),
        [[l["id"], l["name"], l["definition"]] for l in rec["levels"]],
    ]))[:24]


def resolve_gold(rec):
    """Return the level id that ``gold`` refers to, or None.

    akhilaaa3 boolean records carry gold as ``True``/``False`` text while the level ids are
    ``true``/``false``, so an exact match is tried first, then a unique case-insensitive match.
    """
    gold = rec.get("gold")
    if gold is None:
        return None
    ids = [l["id"] for l in rec["levels"]]
    if gold in ids:
        return gold
    folded = [i for i in ids if i.lower() == str(gold).lower()]
    return folded[0] if len(folded) == 1 else None


def _validate(rec, where):
    if not isinstance(rec, dict):
        raise ValueError(f"{where}: record is not an object")
    for key in REQUIRED_FIELDS:
        if key not in rec:
            raise ValueError(f"{where}: missing field {key!r}")
    for key in ("source", "group_id", "task", "qname", "input", "task_definition", "question",
                "level_type", "candidate_set", "variant"):
        if not isinstance(rec[key], str):
            raise ValueError(f"{where}: field {key!r} is not a string")
    if rec["task"] not in TASKS:
        raise ValueError(f"{where}: unknown task {rec['task']!r}")
    if rec["level_type"] not in LEVEL_TYPES:
        raise ValueError(f"{where}: unknown level_type {rec['level_type']!r}")
    levels = rec["levels"]
    if not isinstance(levels, list) or len(levels) < 2:
        raise ValueError(f"{where}: levels must be a list of at least two entries")
    for l in levels:
        if not (isinstance(l, dict) and all(isinstance(l.get(k), str) for k in ("id", "name", "definition"))):
            raise ValueError(f"{where}: malformed level entry")
    pq = rec.get("prefix_questions")
    if pq is not None and not (isinstance(pq, list) and pq and all(isinstance(q, str) for q in pq)):
        raise ValueError(f"{where}: prefix_questions must be a non-empty list of strings")
    if rec["task"] == "T3" and pq is None:
        raise ValueError(f"{where}: T3 record without prefix_questions")
    if len({l["id"] for l in levels}) != len(levels):
        raise ValueError(f"{where}: duplicate level ids")


def load_records(path):
    """Load and validate one task file; derive keys. Returns a list of plain dicts."""
    records = []
    seen = set()
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            rec = json.loads(line)
            _validate(rec, f"{path}:{lineno}")
            rec = dict(rec)
            rec["gold_id"] = resolve_gold(rec)
            rec["unit"] = unit_key(rec)
            rec["key"] = item_key(rec)
            rec["lsv"] = levelset_version(rec["levels"])
            if rec["key"] in seen:
                raise ValueError(f"{path}:{lineno}: duplicate item key")
            seen.add(rec["key"])
            records.append(rec)
    _assign_tau_versions(records)
    return records


def _assign_tau_versions(records):
    """Level-set version that selects a threshold (see thresholds.py).

    T1: the level set exactly as shown (the four name variants are four versions).
    T2: the version of the unit's ``base`` level set, so that a definition swap is judged under the
    same threshold as its base item and the move metric cannot be produced by a threshold change.
    """
    base_lsv = {r["unit"]: r["lsv"] for r in records if r["task"] == "T2" and r["variant"] == "base"}
    for r in records:
        if r["task"] == "T2":
            r["tau_lsv"] = base_lsv.get(r["unit"], r["lsv"])
        else:
            r["tau_lsv"] = r["lsv"]


def swap_positions(variant):
    """Parse ``swap_i_j`` into zero-based list positions (i, j); None for other variants."""
    parts = variant.split("_")
    if len(parts) == 3 and parts[0] == "swap" and parts[1].isdigit() and parts[2].isdigit():
        return int(parts[1]), int(parts[2])
    return None


def task_path(data_root, task, source_file):
    return os.path.join(data_root, TASK_DIRS[task], source_file + ".jsonl")


READOUT_FIELDS = ("task", "variant", "source", "group_id", "qname", "unit", "level_type", "lsv", "tau_lsv")


def make_row(rec, probs):
    """The raw per-item readout that is written to disk and consumed by the metrics.

    ``gold`` is the resolved level id (or None). ``p`` is aligned with ``ids``.
    """
    row = {"k": rec["key"], "ids": [l["id"] for l in rec["levels"]], "gold": rec["gold_id"], "p": list(probs)}
    for f in READOUT_FIELDS:
        row[f] = rec[f]
    return row
