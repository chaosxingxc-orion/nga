#!/usr/bin/env python3
"""R1 SFT data builder (CPU only).

Builds supervised fine-tuning rows from the T1 and T2 task files so that a training prompt is
byte-identical to the evaluation prompt (``prompt.build_prompt``, prompt version r0-prompt-v2,
``record_name`` render).  A row is ``{"prompt": <text ending in "Answer:">, "response": " " + <gold
identifier as rendered>}`` plus provenance.

Eligibility (every condition, no exceptions):
  * the record is on the train side of ``group70`` (hash of ``group_id``);
  * for akhilaaa3 sources it is ALSO on the train side of ``question70`` (hash of ``qname``);
  * the record is a T1 record or a T2 ``base`` record.  T3 is never used.
  * T2 ``swap_*`` / ``reversed`` records are used only in the ``symbol`` arm, and only with the gold
    RECOMPUTED by the definition-follow rule (the gold is the level whose definition text equals the
    definition of the base record's gold level).  The stored gold of those rows is stale
    (R0-BASELINE-PREREG.md 8.4) and is never used.

Arms:
  * ``fixed``  : T1 ``original`` records and T2 ``base`` records as written (original names, declared
                 level order).  T2 base duplicates T1 original byte-for-byte, so duplicates are dropped.
  * ``symbol`` : every eligible record as written, plus K deterministic augmentations of each:
                 fresh identifiers (digits | letters | random 3-6 chars | words from OTHER questions'
                 level names), a random permutation of level order, and with probability p_swap a
                 permutation of the definitions across identifiers where the gold follows the
                 definition.

All randomness comes from ``HashRng`` seeded by sha256(group_id, record index, augmentation index), where
the record index is ``<task>:<line number>`` of the record in its file.  No dependence on the python
version, platform, hash randomisation, dict order or the clock: two builds are byte-identical.

Usage:  python3 -P build_sft.py --arm {fixed,symbol} [--k 2] [--p-swap 0.25] [--max-source-share 0.6]
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # our own sibling modules (prompt.py, split.py copies of r0)

import prompt as prompt_mod  # noqa: E402
from prompt import build_prompt, PROMPT_VERSION  # noqa: E402
from split import GROUP70, QUESTION70, TRAIN, bucket  # noqa: E402

REQUIRED_PROMPT_VERSION = "r0-prompt-v2"
DEFAULT_DATA_ROOT = "/mnt/cephfs/xingchao/experiments/jev"
DEFAULT_OUT_ROOT = "/mnt/cephfs/xingchao/experiments/jev/r1_sft_data"
DEFAULT_TOKENIZER = "/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B/tokenizer.json"
FILES = (("T1", "T1_level_names"), ("T2", "T2_definition_swap"))
SOURCE_FILES = ("typed-decisions", "akhilaaa3", "openjev-synth")  # fixed order
FAMILIES = ("digits", "letters", "random", "words")
OUTPUT_NAME = "train.jsonl"
TAU_CARVEOUT_PREFIX = "r3tau:"   # threshold-fitting carve-out, same bucket convention as split.py
TAU_CARVEOUT_BUCKETS = 1500      # buckets [0, 1500) of 10000 are reserved for threshold fitting
OPENJEV_SOURCE = "openjev-synth"
DEFAULT_OPENJEV_SHARE = 0.40


# --------------------------------------------------------------------------------------- randomness
class HashRng:
    """Deterministic PRNG: a SHA-256 counter stream keyed by the seed parts."""

    def __init__(self, *parts):
        self._key = hashlib.sha256("\x1f".join(str(p) for p in parts).encode("utf-8")).digest()
        self._ctr = 0

    def _u64(self):
        block = hashlib.sha256(self._key + self._ctr.to_bytes(8, "big")).digest()
        self._ctr += 1
        return int.from_bytes(block[:8], "big")

    def randbelow(self, n):
        if n <= 0:
            raise ValueError("randbelow needs n >= 1")
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            x = self._u64()
            if x < limit:
                return x % n

    def random(self):
        return self._u64() / float(1 << 64)

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self.randbelow(i + 1)
            seq[i], seq[j] = seq[j], seq[i]

    def sample(self, seq, k):
        pool = list(seq)
        if k > len(pool):
            raise ValueError("sample larger than population")
        for i in range(k):
            j = i + self.randbelow(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
        return pool[:k]


# --------------------------------------------------------------------------------------- records
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def source_family(source):
    return "akhilaaa3" if source.startswith("akhilaaa3") else source


def tau_carved(group_id):
    """True when the group is reserved for threshold fitting (never used for SFT)."""
    return bucket(TAU_CARVEOUT_PREFIX + group_id) < TAU_CARVEOUT_BUCKETS


def is_train_everywhere(rec):
    """Train side of group70 and, for akhilaaa3, also of question70 (both conditions)."""
    if GROUP70.assign(rec) != TRAIN:
        return False
    if source_family(rec["source"]) == "akhilaaa3" and QUESTION70.assign(rec) != TRAIN:
        return False
    return True


def resolve_gold_index(rec):
    """Index in ``rec['levels']`` of the level ``rec['gold']`` refers to, or None.

    Exact id match first; otherwise a unique case-insensitive match (akhilaaa3 boolean records carry
    gold as ``True``/``False`` while the ids are lowercase).
    """
    ids = [l["id"] for l in rec["levels"]]
    gold = rec.get("gold")
    if gold is None:
        return None
    if gold in ids:
        return ids.index(gold) if ids.count(gold) == 1 else None
    folded = [i for i, x in enumerate(ids) if x.lower() == str(gold).lower()]
    return folded[0] if len(folded) == 1 else None


def recompute_gold_by_definition(base_rec, var_rec):
    """Definition-follow rule for T2 swap / reversed records.

    Returns the index in ``var_rec['levels']`` of the level whose definition text equals the
    definition of ``base_rec``'s gold level, or None if the base gold does not resolve or the
    definition text is not carried by exactly one level of ``var_rec``.
    """
    gi = resolve_gold_index(base_rec)
    if gi is None:
        return None
    gdef = base_rec["levels"][gi]["definition"]
    hits = [i for i, l in enumerate(var_rec["levels"]) if l["definition"] == gdef]
    return hits[0] if len(hits) == 1 else None


def input_key(rec):
    return hashlib.sha256(rec["input"].encode("utf-8")).hexdigest()


def load_eligible(data_root, arm, t2_swaps, limit_groups=None, stats=None, tau_carveout=True,
                  drop_openjev_digits=False):
    """Return the list of eligible records (dicts) in deterministic order, each tagged with
    ``_task``, ``_rec_index``, ``_file`` and ``_gold_index`` (index into levels of the correct gold).
    """
    stats = stats if stats is not None else {}
    bump = lambda k, n=1: stats.__setitem__(k, stats.get(k, 0) + n)
    out = []
    for task, dirname in FILES:
        for sf in SOURCE_FILES:
            path = os.path.join(data_root, dirname, sf + ".jsonl")
            base_by_key = {}   # T2: (group_id, qname, input hash) -> base record
            pending = []       # T2 swap/reversed rows needing their base
            with open(path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f):
                    rec = json.loads(line)
                    bump("seen_records")
                    if not is_train_everywhere(rec):
                        bump("excluded_heldout_side")
                        continue
                    if tau_carveout and tau_carved(rec["group_id"]):
                        bump("excluded_tau_carveout")
                        continue
                    if (drop_openjev_digits and task == "T1" and rec["variant"] == "digits"
                            and source_family(rec["source"]) == OPENJEV_SOURCE):
                        bump("excluded_openjev_t1_digits")
                        continue
                    if rec.get("candidate_set") != "exclusive":
                        bump("excluded_not_exclusive")
                        continue
                    rec["_task"], rec["_rec_index"], rec["_file"] = task, f"{task}:{line_no}", f"{dirname}/{sf}.jsonl"
                    variant = rec["variant"]
                    if task == "T1":
                        if arm == "fixed" and variant != "original":
                            bump("excluded_fixed_arm_non_original")
                            continue
                        rec["_gold_index"] = resolve_gold_index(rec)
                        rec["_gold_recomputed"] = False
                        if rec["_gold_index"] is None:
                            bump("excluded_gold_unresolvable")
                            continue
                        out.append(rec)
                    else:  # T2
                        key = (rec["group_id"], rec["qname"], input_key(rec))
                        if variant == "base":
                            base_by_key[key] = rec
                            rec["_gold_index"] = resolve_gold_index(rec)
                            rec["_gold_recomputed"] = False
                            if rec["_gold_index"] is None:
                                bump("excluded_gold_unresolvable")
                                continue
                            out.append(rec)
                        elif arm == "symbol" and t2_swaps == "recomputed":
                            pending.append((key, rec))
                        else:
                            bump("excluded_t2_swap_or_reversed")
            for key, rec in pending:
                base = base_by_key.get(key)
                gi = recompute_gold_by_definition(base, rec) if base is not None else None
                if gi is None:
                    bump("excluded_t2_swap_gold_not_recomputable")
                    continue
                rec["_gold_index"], rec["_gold_recomputed"] = gi, True
                bump("t2_swap_gold_recomputed")
                if resolve_gold_index(rec) != gi:
                    bump("t2_swap_stored_gold_differs_from_recomputed")
                out.append(rec)
    if limit_groups:
        keep = {}
        for fam in SOURCE_FILES:
            gids = sorted({r["group_id"] for r in out if source_family(r["source"]) == fam},
                          key=lambda g: hashlib.sha256(("limit|" + g).encode()).hexdigest())
            keep[fam] = set(gids[:limit_groups])
        out = [r for r in out if r["group_id"] in keep[source_family(r["source"])]]
        stats["limit_groups_per_source"] = limit_groups
    return out


# --------------------------------------------------------------------------------------- augmentation
def build_word_pool(records):
    """Level names of train-side T1 ``original`` records, with the qnames that use each name.

    Only train-eligible records feed the pool, so no held-out level name is introduced.
    """
    users = {}
    for r in records:
        if r["_task"] == "T1" and r["variant"] == "original":
            for l in r["levels"]:
                nm = l["name"]
                if any(c.isalpha() for c in nm) and len(nm) >= 2 and "\n" not in nm:
                    users.setdefault(nm, set()).add(r["qname"])
    words = sorted(users)
    return words, users


def _letters(rng, n):
    lower = rng.randbelow(2) == 0
    alpha = "abcdefghijklmnopqrstuvwxyz" if lower else "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if n <= 26:
        return rng.sample(list(alpha), n)
    two = [a + b for a in alpha for b in alpha]
    return rng.sample(two, n)


def _digits(rng, n):
    return [str(x) for x in rng.sample(list(range(0, max(10, n + 6))), n)]


def _random_strings(rng, n):
    alpha = "abcdefghijklmnopqrstuvwxyz0123456789"
    seen, out = set(), []
    while len(out) < n:
        s = "".join(alpha[rng.randbelow(len(alpha))] for _ in range(3 + rng.randbelow(4)))
        if s not in seen and not s.isdigit():
            seen.add(s)
            out.append(s)
    return out


def _words(rng, n, pool, users, qname):
    out, seen, tries = [], set(), 0
    while len(out) < n:
        w = pool[rng.randbelow(len(pool))]
        tries += 1
        if w in seen or qname in users[w]:
            if tries > 50 * n + 1000:
                raise RuntimeError("word pool too small for rejection sampling")
            continue
        seen.add(w)
        out.append(w)
    return out


def make_identifiers(rng, family, n, pool, users, qname):
    if family == "digits":
        return _digits(rng, n)
    if family == "letters":
        return _letters(rng, n)
    if family == "random":
        return _random_strings(rng, n)
    if family == "words":
        return _words(rng, n, pool, users, qname)
    raise ValueError(family)


def augment_record(rec, aug_index, p_swap, pool, users, force_swap=None, families=FAMILIES):
    """One deterministic augmentation of ``rec``. Returns (new_record, info).

    Steps (all from one HashRng keyed by group_id, record index, augmentation index):
      1. draw a fresh identifier family and n distinct identifiers (slot i gets identifier ids[i]);
      2. with probability p_swap permute the definitions across the slots (non-identity); the gold
         identifier is the identifier now attached to the original gold definition;
      3. permute the declared level order.
    """
    rng = HashRng(rec["group_id"], rec["_rec_index"], aug_index)
    levels = rec["levels"]
    n = len(levels)
    gi = rec["_gold_index"]
    family = families[rng.randbelow(len(families))]
    ids = make_identifiers(rng, family, n, pool, users, rec["qname"])
    defs = [l["definition"] for l in levels]
    swap = (rng.random() < p_swap) if force_swap is None else force_swap
    defs_permuted = False
    gold_slot = gi
    slot_defs = list(defs)
    if swap and n >= 2:
        for _ in range(16):
            perm = list(range(n))
            rng.shuffle(perm)
            if perm != list(range(n)):
                break
        else:  # vanishingly unlikely: force a rotation
            perm = list(range(1, n)) + [0]
        # slot s now carries the definition of original level perm[s]
        slot_defs = [defs[perm[s]] for s in range(n)]
        gold_slot = perm.index(gi)
        defs_permuted = True
    order = list(range(n))
    rng.shuffle(order)
    new_levels = [{"id": ids[s], "name": ids[s], "definition": slot_defs[s]} for s in order]
    new_gold_pos = order.index(gold_slot)
    new = {k: v for k, v in rec.items() if not k.startswith("_")}
    new["levels"] = new_levels
    new["gold"] = ids[gold_slot]
    new["_task"], new["_rec_index"], new["_file"] = rec["_task"], rec["_rec_index"], rec["_file"]
    new["_gold_index"] = new_gold_pos
    new["_gold_recomputed"] = bool(rec.get("_gold_recomputed", False))
    info = {"augmentation": family, "aug_index": aug_index, "order_permuted": True,
            "defs_permuted": defs_permuted}
    return new, info


# --------------------------------------------------------------------------------------- rows
def make_row(rec, arm, info, group_unit):
    p = build_prompt(rec, render="record_name")
    gi = rec["_gold_index"]
    response = p.candidates[gi]  # " " + the gold level's identifier as rendered
    assert p.text.endswith("Answer:") and response == " " + p.labels[gi]
    row = {
        "prompt": p.text,
        "response": response,
        "source": rec["source"],
        "source_family": source_family(rec["source"]),
        "task": rec["_task"],
        "variant": rec["variant"],
        "group_id": rec["group_id"],
        "qname": rec["qname"],
        "level_type": rec["level_type"],
        "arm": arm,
        "augmentation": info["augmentation"],
        "aug_index": info["aug_index"],
        "order_permuted": info["order_permuted"],
        "defs_permuted": info["defs_permuted"],
        "gold_recomputed": bool(rec.get("_gold_recomputed", False)),
        "n_levels": len(rec["levels"]),
        "prompt_version": PROMPT_VERSION,
        "rec_index": rec["_rec_index"],
        "file": rec["_file"],
    }
    return row


def row_sort_key(row):
    return hashlib.sha256(f"{row['group_id']}\x1f{row['rec_index']}\x1f{row['aug_index']}".encode()).hexdigest()


def build_rows(records, arm, k, p_swap, no_digits_family_sources=()):
    plain = {"augmentation": "none", "aug_index": -1, "order_permuted": False, "defs_permuted": False}
    dropped_dup = 0
    seen = set()
    rows = []
    pool, users = build_word_pool(records) if arm == "symbol" else ([], {})
    for rec in records:
        row = make_row(rec, arm, plain, None)
        dk = (row["prompt"], row["response"])
        if dk in seen:  # e.g. T2 base is byte-identical to T1 original
            dropped_dup += 1
            continue
        seen.add(dk)
        rows.append(row)
        if arm == "symbol":
            for a in range(k):
                fams = FAMILIES
                if source_family(rec["source"]) in no_digits_family_sources:
                    fams = tuple(f for f in FAMILIES if f != "digits")
                new, info = augment_record(rec, a, p_swap, pool, users, families=fams)
                arow = make_row(new, arm, info, None)
                adk = (arow["prompt"], arow["response"])
                if adk in seen:
                    dropped_dup += 1
                    continue
                seen.add(adk)
                rows.append(arow)
    return rows, dropped_dup


def apply_source_cap(rows, max_share, per_family=None):
    """Subsample whole groups of any source family whose row share exceeds ``max_share``.

    Groups are taken in sha256 order of ``group_id`` so the selection is stable. Returns
    (rows, report).
    """
    def counts(rs):
        c = {}
        for r in rs:
            c[r["source_family"]] = c.get(r["source_family"], 0) + 1
        return c
    before = counts(rows)
    per_family = dict(per_family or {})
    cap_of = lambda fam: per_family.get(fam, max_share)
    report = {"max_source_share": max_share, "per_family_max_share": per_family, "rows_before_cap": before,
              "capped": {}}
    cur = rows
    for _ in range(len(before) + 1):
        c = counts(cur)
        total = sum(c.values())
        over = [f for f in sorted(c) if c[f] / total > cap_of(f) + 1e-12]
        if not over:
            break
        fam = over[0]
        others = total - c[fam]
        if others == 0:
            report["cap_skipped"] = f"{fam} is the only source present"
            break
        allowed = int(cap_of(fam) / (1.0 - cap_of(fam)) * others)
        per_group = {}
        for r in cur:
            if r["source_family"] == fam:
                per_group[r["group_id"]] = per_group.get(r["group_id"], 0) + 1
        kept, used = set(), 0
        for g in sorted(per_group, key=lambda g: hashlib.sha256(("cap|" + g).encode()).hexdigest()):
            if used + per_group[g] > allowed:
                continue
            kept.add(g)
            used += per_group[g]
        cur = [r for r in cur if r["source_family"] != fam or r["group_id"] in kept]
        report["capped"][fam] = {"allowed_rows": allowed, "kept_rows": used, "kept_groups": len(kept),
                                 "dropped_groups": len(per_group) - len(kept)}
    report["rows_after_cap"] = counts(cur)
    tot = sum(report["rows_after_cap"].values())
    report["row_share_after_cap"] = {f: round(v / tot, 6) for f, v in sorted(report["rows_after_cap"].items())}
    return cur, report


# --------------------------------------------------------------------------------------- verification
def verify_output(path, data_root, tau_carveout=True, drop_openjev_digits=False, drop_openjev_digits_family=False):
    """Re-read an output file and check every row against the frozen split and the prompt builder.

    Returns a dict of violation counts (all zero when correct).
    """
    viol = {"rows": 0, "heldout_group70": 0, "heldout_question70": 0, "t3_rows": 0,
            "prompt_mismatch_unaugmented": 0, "prompt_not_ending_answer": 0, "response_not_in_options": 0,
            "stale_gold_row_used": 0, "bad_prompt_version": 0, "tau_carved_group": 0,
            "openjev_t1_digits_row": 0, "openjev_digits_family_augmentation": 0}
    cache = {}

    def line_of(fname, idx):
        if fname not in cache:
            with open(os.path.join(data_root, fname), "r", encoding="utf-8") as f:
                cache[fname] = f.readlines()
        return json.loads(cache[fname][idx])

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            viol["rows"] += 1
            if GROUP70.assign({"group_id": row["group_id"]}) != TRAIN:
                viol["heldout_group70"] += 1
            if row["source_family"] == "akhilaaa3" and QUESTION70.assign({"qname": row["qname"]}) != TRAIN:
                viol["heldout_question70"] += 1
            if tau_carveout and tau_carved(row["group_id"]):
                viol["tau_carved_group"] += 1
            if (drop_openjev_digits and row["task"] == "T1" and row["variant"] == "digits"
                    and row["source_family"] == OPENJEV_SOURCE):
                viol["openjev_t1_digits_row"] += 1
            if (drop_openjev_digits_family and row["augmentation"] == "digits"
                    and row["source_family"] == OPENJEV_SOURCE):
                viol["openjev_digits_family_augmentation"] += 1
            if row["task"] not in ("T1", "T2") or row["file"].startswith("T3"):
                viol["t3_rows"] += 1
            if row["prompt_version"] != REQUIRED_PROMPT_VERSION:
                viol["bad_prompt_version"] += 1
            if not row["prompt"].endswith("Answer:"):
                viol["prompt_not_ending_answer"] += 1
            opts = [ln[2:].split(":", 1)[0] for ln in row["prompt"].split("\nOptions:\n", 1)[1].split("\n\n", 1)[0].split("\n")]
            if not row["response"].startswith(" ") or row["response"][1:] not in opts:
                viol["response_not_in_options"] += 1
            if row["task"] == "T2" and row["variant"] != "base" and not row["gold_recomputed"]:
                viol["stale_gold_row_used"] += 1
            if row["augmentation"] == "none":
                rec = line_of(row["file"], int(row["rec_index"].split(":")[1]))
                if build_prompt(rec, render="record_name").text != row["prompt"]:
                    viol["prompt_mismatch_unaugmented"] += 1
    return viol


# --------------------------------------------------------------------------------------- manifest
def count_by(rows, keys):
    c = {}
    for r in rows:
        k = "|".join(str(r[x]) for x in keys)
        c[k] = c.get(k, 0) + 1
    return dict(sorted(c.items()))


def token_totals(rows, tokenizer_path):
    try:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(tokenizer_path)
    except Exception as e:  # tokenizers not installed, or tokenizer file missing
        return {"available": False, "reason": f"{type(e).__name__}"}
    tot = {"available": True, "tokenizer": tokenizer_path, "prompt_tokens": 0, "response_tokens": 0,
           "per_source_family_prompt_plus_response": {}, "max_prompt_tokens": 0}
    B = 512
    for i in range(0, len(rows), B):
        chunk = rows[i:i + B]
        pe = tok.encode_batch([r["prompt"] for r in chunk])
        re_ = tok.encode_batch([r["response"] for r in chunk])
        for r, p, q in zip(chunk, pe, re_):
            tot["prompt_tokens"] += len(p.ids)
            tot["response_tokens"] += len(q.ids)
            tot["max_prompt_tokens"] = max(tot["max_prompt_tokens"], len(p.ids))
            d = tot["per_source_family_prompt_plus_response"]
            d[r["source_family"]] = d.get(r["source_family"], 0) + len(p.ids) + len(q.ids)
    tot["total_tokens"] = tot["prompt_tokens"] + tot["response_tokens"]
    tot["per_source_family_prompt_plus_response"] = dict(sorted(tot["per_source_family_prompt_plus_response"].items()))
    return tot


def realized_mix(rows):
    n = len(rows) or 1
    share = lambda c: {k: round(v / n, 6) for k, v in c.items()}
    return {"rows": len(rows),
            "share_by_source_family": share(count_by(rows, ["source_family"])),
            "share_by_source_family_task_variant": share(count_by(rows, ["source_family", "task", "variant"])),
            "share_by_augmentation": share(count_by(rows, ["augmentation"])),
            "share_by_level_type": share(count_by(rows, ["level_type"]))}


def code_hashes():
    return {n: sha256_file(os.path.join(HERE, n)) for n in ("build_sft.py", "prompt.py", "split.py")}


def build(args):
    if PROMPT_VERSION != REQUIRED_PROMPT_VERSION:
        raise SystemExit(f"prompt version {PROMPT_VERSION!r} != required {REQUIRED_PROMPT_VERSION!r}")
    arm = args.arm
    t2_swaps = args.t2_swaps if arm == "symbol" else "none"
    stats = {}
    # Composition rules that exist only in the symbol arm (orchestrator, 2026-10-30): no openjev-synth T1
    # `digits` rows and a lower share cap for openjev-synth.
    drop_digits = (arm == "symbol") and args.symbol_drop_openjev_digits
    per_family = {OPENJEV_SOURCE: args.openjev_max_share} if arm == "symbol" else {}
    records = load_eligible(args.data_root, arm, t2_swaps, args.limit_groups, stats,
                            tau_carveout=args.tau_carveout, drop_openjev_digits=drop_digits)
    drop_family = (arm == "symbol") and args.symbol_drop_openjev_digits_family
    rows, dropped_dup = build_rows(records, arm, args.k if arm == "symbol" else 0, args.p_swap,
                                   (OPENJEV_SOURCE,) if drop_family else ())
    rows, cap_report = apply_source_cap(rows, args.max_source_share, per_family)
    rows.sort(key=row_sort_key)
    out_dir = os.path.join(args.out_root, arm)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, OUTPUT_NAME)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    viol = verify_output(out_path, args.data_root, args.tau_carveout, drop_digits, drop_family)
    ok = all(v == 0 for k, v in viol.items() if k != "rows")
    manifest = {
        "arm": arm,
        "prompt_version": PROMPT_VERSION,
        "render": "record_name",
        "args": {"arm": arm, "k": args.k if arm == "symbol" else 0, "p_swap": args.p_swap,
                 "max_source_share": args.max_source_share, "t2_swaps": t2_swaps,
                 "tau_carveout": args.tau_carveout, "tau_carveout_rule": f"bucket(sha256({TAU_CARVEOUT_PREFIX!r}+group_id)) < {TAU_CARVEOUT_BUCKETS}",
                 "symbol_drop_openjev_digits": drop_digits,
                 "symbol_drop_openjev_digits_family": drop_family,
                 "per_family_max_share": per_family,
                 "limit_groups": args.limit_groups, "data_root": args.data_root},
        "relaunch": "python3 -P " + os.path.join(HERE, "build_sft.py") + " " + " ".join(sys.argv[1:]),
        "rows": len(rows),
        "counts_by_source_family": count_by(rows, ["source_family"]),
        "counts_by_source": count_by(rows, ["source"]),
        "realized_mix": realized_mix(rows),
        "counts_by_task_variant": count_by(rows, ["task", "variant"]),
        "counts_by_source_family_task_variant_augmentation": count_by(rows, ["source_family", "task", "variant", "augmentation"]),
        "counts_by_augmentation": count_by(rows, ["augmentation"]),
        "counts_by_level_type": count_by(rows, ["level_type"]),
        "counts_by_defs_permuted": count_by(rows, ["defs_permuted"]),
        "counts_by_gold_recomputed": count_by(rows, ["gold_recomputed"]),
        "load_stats": stats,
        "dropped_duplicate_prompt_response": dropped_dup,
        "source_cap": cap_report,
        "tokens": token_totals(rows, args.tokenizer),
        "verification": dict(viol, passed=ok),
        "code_sha256": code_hashes(),
        "output_sha256": {OUTPUT_NAME: sha256_file(out_path)},
        "input_sha256": {os.path.join(d, sf + ".jsonl"): sha256_file(os.path.join(args.data_root, d, sf + ".jsonl"))
                         for _, d in FILES for sf in SOURCE_FILES},
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({"arm": arm, "rows": len(rows), "out": out_path, "verification_passed": ok,
                      "share": cap_report["row_share_after_cap"]}, sort_keys=True))
    return 0 if ok else 2


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arm", required=True, choices=("fixed", "symbol"))
    ap.add_argument("--k", type=int, default=2, help="augmentations per train record (symbol arm)")
    ap.add_argument("--p-swap", type=float, default=0.25, help="probability that an augmentation permutes definitions")
    ap.add_argument("--max-source-share", type=float, default=0.6, help="cap on any source family's row share")
    ap.add_argument("--tau-carveout", action=argparse.BooleanOptionalAction, default=True,
                    help="exclude groups reserved for threshold fitting: bucket(sha256('r3tau:'+group_id)) < 1500 (default on)")
    ap.add_argument("--openjev-max-share", type=float, default=DEFAULT_OPENJEV_SHARE,
                    help="symbol arm: cap on the openjev-synth row share (default 0.40)")
    ap.add_argument("--symbol-drop-openjev-digits", action=argparse.BooleanOptionalAction, default=True,
                    help="symbol arm: drop openjev-synth T1 `digits` rows and their augmentations (default on)")
    ap.add_argument("--symbol-drop-openjev-digits-family", action=argparse.BooleanOptionalAction, default=True,
                    help="symbol arm: never draw the `digits` identifier family for openjev-synth augmentations "
                         "(count definitions conflict with digit labels; R0 section 12.3) (default on)")
    ap.add_argument("--t2-swaps", choices=("recomputed", "none"), default="recomputed",
                    help="symbol arm: include T2 swap/reversed rows with the gold recomputed by definition")
    ap.add_argument("--limit-groups", type=int, default=None, help="debug: keep N groups per source family")
    ap.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    ap.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    ap.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    return ap.parse_args(argv)


if __name__ == "__main__":
    sys.exit(build(parse_args()))
