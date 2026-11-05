"""Kev stage-1 training-time augmentation, ported verbatim and applied to converted rows.

Everything here is pure Python (no torch), so it runs on the host and in tests.

Source of truth: /mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev, commit 2074cc44256200bb37540103fa4572901faa10f3.
  kev/data.py:20-21    source_seed(seed, source)            -> the per-stream seed hash
  kev/data.py:51-56    NONE_OPTIONS, DISTRACTORS             -> the none-of-the-above texts and the distractors
  kev/data.py:320-343  augment(req, rng, p_none, p_none_distract, p_distract)
  kev/data.py:346-357  none_pair(req, rng)                   -> the none-present / none-absent minimal pair
  kev/train.py:295-302 record_variants: item_rng = Random(source_seed(seed, f"{epoch}:{record id}")) is created
                       once per RECORD and EPOCH; augment() draws from it, then (p_none_pair) a coin and none_pair().
  kev/train.py:607     records are reshuffled every epoch (rng.shuffle(reqs)).
  experiments/q35-08b.json  p_none_pair = 0.25; augment defaults p_none=0.1, p_none_distract=0.12, p_distract=0.15
                       (kev/train.py:400-403).

Fidelity: `augment` and `none_pair` below are line-for-line copies of Kev's functions and operate on Kev-shaped
requests ({"state", "questions": {qid: {"type", "criteria", "label", ...}}}); `test_r3.py` extracts the originals
from Kev's data.py with `ast` (no import of Kev, whose module needs `datasets`) and asserts identical outputs on
every decision-v7 training record for several (seed, epoch) pairs.

Randomness: one `random.Random(source_seed(seed, f"{epoch}:{record id}"))` per Kev RECORD and epoch, consumed in
question order exactly as Kev does. A question's augmentation is therefore a deterministic function of
(seed, epoch, record id, the position of the question among the record's choice questions).

What Kev augments: `choice` questions only (option shuffle always; a none-of-the-above option inserted as the correct
answer with p_none, as a wrong alternative with p_none_distract; an irrelevant distractor with p_distract). `noul`
(yes/no) and `score` (ordinal) questions are passed through unchanged, order included (kev/data.py:326-327).
"""
import copy
import hashlib
import random

# ---- kev/data.py:51-56, verbatim -------------------------------------------------------------------------------
NONE_OPTIONS = [("other", "None of the above"), ("other", "A reason that fits none of the above"), ("none", "None of these"),
                ("other", "Something else"), ("not_listed", "Not listed here"), ("none_of_the_above", None),
                ("other", "A category that fits none of the above"), ("other", "None of the listed options apply"),
                ("unknown", "Cannot be determined from the options given"), ("other", "Other"), ("none", None),
                ("other", "An answer not covered by the other options"), ("no_match", "No option matches")]
DISTRACTORS = {"weather": "Bad weather caused it", "purple": "The colour purple", "pancakes": "A recipe for pancakes", "taxes": "Unrelated: quarterly tax filing"}

KEV_DEFAULTS = {"p_none": 0.1, "p_none_distract": 0.12, "p_distract": 0.15, "p_none_pair": 0.25}


def source_seed(seed, source):
    """kev/data.py:20-21, verbatim."""
    return int.from_bytes(hashlib.sha256(f"{seed}:{source}".encode()).digest()[:8], "big")


# ---- kev/data.py:320-343, verbatim (docstring shortened) ---------------------------------------------------------
def augment(req, rng, p_none=0.1, p_none_distract=0.12, p_distract=0.15):
    if min(p_none, p_none_distract, p_distract) < 0 or p_none + p_none_distract + p_distract > 1:
        raise ValueError("augmentation probabilities must be nonnegative and sum to at most one")
    out = {"state": req["state"], "questions": {}}
    for qid, q in req["questions"].items():
        if q["type"] != "choice":
            out["questions"][qid] = q; continue
        crit, y = dict(q["criteria"]), q["label"]
        if q.get("target") is not None:                       # soft-target questions: permute only; inserting or swapping options would change the target's meaning
            keys = list(crit); rng.shuffle(keys); out["questions"][qid] = {**q, "criteria": {k: crit[k] for k in keys}}; continue
        r = rng.random()
        none_options = [(k, v) for k, v in NONE_OPTIONS if k not in crit]
        distractors = [k for k in DISTRACTORS if k not in crit]
        if len(crit) > 2 and r < p_none and none_options:
            nk, nd = rng.choice(none_options); crit.pop(y); crit[nk] = nd; y = nk
        elif p_none <= r < p_none + p_none_distract and len(crit) < 255 and none_options:
            nk, nd = rng.choice(none_options); crit[nk] = nd
        elif p_none + p_none_distract <= r < p_none + p_none_distract + p_distract and len(crit) < 255 and distractors:
            k = rng.choice(distractors); crit[k] = DISTRACTORS[k]
        keys = list(crit); rng.shuffle(keys)
        out["questions"][qid] = {**q, "criteria": {k: crit[k] for k in keys}, "label": y}
    return out


# ---- kev/data.py:346-357, verbatim (docstring shortened) ---------------------------------------------------------
def none_pair(req, rng):
    eligible = [(qid, q) for qid, q in req["questions"].items() if q["type"] == "choice" and len(q["criteria"]) >= 3 and q.get("target") is None]
    if not eligible: return []
    qid, q = rng.choice(eligible)
    nk, nd = rng.choice([o for o in NONE_OPTIONS if o[0] not in q["criteria"]] or [("none_of_these", None)])
    keys = list(q["criteria"]) + [nk]; rng.shuffle(keys)
    present = {**q, "criteria": {k: (nd if k == nk else q["criteria"][k]) for k in keys}}
    absent = {**present, "criteria": {k: v for k, v in present["criteria"].items() if k != q["label"]}, "label": nk}
    return [{"state": req["state"], "questions": {qid: present}}, {"state": req["state"], "questions": {qid: absent}}]


# ---- converted rows <-> Kev-shaped requests ----------------------------------------------------------------------
def record_key(row):
    """Rows of one Kev record share (suite, split, kev.line)."""
    k = row["kev"]
    return (k["suite"], row["split"], k["line"])


def group_records(rows):
    """[(record key, [rows in question order])] in file order. Asserts question order is the qindex order."""
    out, index = [], {}
    for r in rows:
        key = record_key(r)
        if key not in index:
            index[key] = len(out)
            out.append((key, []))
        out[index[key]][1].append(r)
    for key, rs in out:
        assert [r["kev"]["qindex"] for r in rs] == list(range(len(rs))), key
    return out


def to_kev_request(rows):
    """Kev-shaped request from the converted rows of one record. Only what augment/none_pair read is rebuilt:
    type, criteria (choice only: key -> description or None), label. The state is not needed."""
    qs = {}
    for r in rows:
        qtype = r["kev"]["qtype"]
        q = {"type": qtype, "_row": r}
        if r["kev"].get("has_target"):
            q["target"] = True   # soft-target marker; decision-v7 train has none, the branch is kept for fidelity
        if qtype == "choice":
            q["criteria"] = {l["id"]: (None if l["shown"] == l["name"] else l["definition"]) for l in r["levels"]}
            q["label"] = r["gold"]
        qs[r["qname"]] = q
    return {"state": None, "questions": qs}


def row_from_question(base_row, q, qname, tag):
    """Converted row for an augmented / generated question. Unchanged questions return the original row."""
    if q["type"] != "choice":
        return base_row
    row = copy.deepcopy(base_row)
    row["qname"] = qname
    levels = []
    for key, desc in q["criteria"].items():
        has = not (desc is None or desc == "")
        levels.append({"id": key, "name": key, "definition": desc if has else key, "shown": f"{key}: {desc}" if has else key})
    row["levels"] = levels
    row["gold"] = q["label"]
    row["kev"] = dict(row["kev"], aug=tag)
    return row


def classify(orig_criteria, new_criteria, new_label, orig_label):
    """Which Kev augmentation branch fired, read back from the result (provenance only)."""
    added = [k for k in new_criteria if k not in orig_criteria]
    if new_label != orig_label:
        mode = "none_correct"
    elif added and added[0] in DISTRACTORS and DISTRACTORS.get(added[0]) == new_criteria[added[0]]:
        mode = "distractor"
    elif added:
        mode = "none_wrong"
    else:
        mode = "shuffle_only"
    return mode


def augment_record(rows, seed, epoch, p_none=0.1, p_none_distract=0.12, p_distract=0.15, p_none_pair=0.25):
    """Kev's per-record, per-epoch variants as converted rows: [augmented rows of the record..., pair rows...].

    Mirrors kev/train.py:295-302 (record_variants with pairs=None): the stream is created once, augment() consumes it,
    then one coin for the pair and none_pair() from the SAME stream.
    """
    req = to_kev_request(rows)
    rid = rows[0]["kev"]["id"]
    item_rng = random.Random(source_seed(seed, f"{epoch}:{rid}"))
    aug = augment(req, item_rng, p_none=p_none, p_none_distract=p_none_distract, p_distract=p_distract)
    out = []
    for r in rows:
        q0, q1 = req["questions"][r["qname"]], aug["questions"][r["qname"]]
        if q0["type"] == "choice":
            tag = {"mode": classify(q0["criteria"], q1["criteria"], q1["label"], q0["label"]), "epoch": epoch, "kind": "main"}
        else:
            tag = None
        out.append(row_from_question(r, q1, r["qname"], tag))
    if p_none_pair > 0 and item_rng.random() < p_none_pair:
        pair = none_pair(req, item_rng)
        for kind, p in zip(("none_present", "none_absent"), pair):
            (qname, q), = p["questions"].items()
            base = req["questions"][qname]["_row"]
            out.append(row_from_question(base, q, qname, {"mode": kind, "epoch": epoch, "kind": "pair"}))
    return out


def augment_epoch(rows, seed, epoch, **probs):
    """All rows of an epoch after Kev augmentation, record order = file order (shuffling is the caller's job)."""
    out = []
    for _, rs in group_records(rows):
        out.extend(augment_record(rs, seed, epoch, **probs))
    return out
