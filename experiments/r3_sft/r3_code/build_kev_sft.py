"""Build the per-epoch SFT rows for round 1 (R3-SFT-PREREG §7.2, §3.1, §3.3).

    python3 -I build_kev_sft.py --out-dir <dir> --seed 2 --epochs 2 [--augment none|kev] [--drop-state] [--limit N]

Input : decision-v7 train rows converted by r1_code/convert_kev.py (one row per question).
Output: <out-dir>/train.e<epoch>.jsonl, one JSON object per training example, in the order the trainer consumes them:
        {"prompt": str, "response": " " + gold name, "candidates": [" " + name_i ...], "gold_index": int,
         "prov": {...}}
        plus <out-dir>/manifest.json (input/output sha256, counts, args, code hashes, gold-position distribution).

prompt   = r0 prompt.build_prompt(record, render="record_name"), the renderer the evaluation scorer uses (R3 prereg
           §3.1). With --drop-state the input section is removed through prompt.drop_input (arm K1-QO).
response = " " + the gold level's name (the identifier the scorer reads, prereg §3.2). The trainer tokenizes the
           prompt and the response separately and concatenates the ids, as the scorer does; the loss mask is on the
           response tokens only and no EOS token is ever appended (prereg §7.2 ruling).
candidates / gold_index: the question's options, in prompt order, for the option-restricted loss K2 (§7.3).

--augment kev (default, frozen prereg 387521b §3.4): Kev's stage-1 augmentation exactly as in kev/data.py:320-357 and
                kev/train.py:295-302 (see kev_aug.py): option shuffle on every choice question, none-of-the-above /
                distractor insertion at Kev's rates (0.10 / 0.12 / 0.15), and with p = 0.25 a none-present /
                none-absent minimal pair per record, regenerated every epoch from
                Random(source_seed(seed, f"{epoch}:{record id}")). A pair's two rows are SIBLINGS of the base question
                that produced them: they ride in that question's optimizer step and do not count toward the batch
                (§3.4 last bullets; §7.2 "10 base questions per optimizer step").
--augment none: converted rows unchanged (debug/ablation only; no frozen arm uses it).

Units: epoch_units() returns [[base example, sibling examples...], ...] in the epoch's shuffled order; one unit is one
base question. The trainer takes 10 consecutive units per optimizer step (§7.2).

Example order within an epoch: a deterministic shuffle of the epoch's rows, Random(source_seed(seed, f"shuffle:{epoch}")).
"""
import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
R0_CODE = "/mnt/cephfs/xingchao/experiments/jev/r0_code"
DEFAULT_TRAIN = "/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl"

import kev_aug  # noqa: E402


def load_prompt_module(prompt_dir):
    if prompt_dir not in sys.path:
        sys.path.insert(0, prompt_dir)
    import prompt as prompt_mod
    return prompt_mod


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_rows(path, limit=0):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
                if limit and len(rows) >= limit:
                    break
    return rows


def make_example(row, prompt_mod, drop_state):
    """One training example from one (possibly augmented) converted row."""
    rec = prompt_mod.drop_input(row) if drop_state else row
    p = prompt_mod.build_prompt(rec, render="record_name")
    names = {l["id"]: l["name"] for l in row["levels"]}
    gold_idx = [l["id"] for l in row["levels"]].index(row["gold"])
    response = " " + names[row["gold"]]
    assert response == p.candidates[gold_idx], (response, p.candidates[gold_idx])
    assert len(set(p.candidates)) == len(p.candidates), "duplicate candidate strings in one question"
    k = row["kev"]
    prov = {"suite": k["suite"], "split": row["split"], "line": k["line"], "qindex": k["qindex"], "id": k["id"],
            "source": row["source"], "qname": row["qname"], "level_type": row["level_type"], "n_options": len(p.candidates),
            "gold_index": gold_idx, "prompt_version": p.version, "aug": k.get("aug")}
    return {"prompt": p.text, "response": response, "candidates": list(p.candidates), "gold_index": gold_idx, "prov": prov}


def epoch_units(rows, seed, epoch, augment="kev", prompt_mod=None, drop_state=False):
    """[[example, sibling examples...], ...] for one epoch, shuffled by seed (prereg §3.4, §7.2).

    Each base question is the converted row's (possibly augmented) main variant; pair siblings are attached to the
    base question whose qname produced them. Unit order: Random(source_seed(seed, f"shuffle:{epoch}")).
    """
    prompt_mod = prompt_mod or load_prompt_module(R0_CODE)
    units = []
    for _, rs in kev_aug.group_records(rows):
        if augment == "kev":
            out = kev_aug.augment_record(rs, seed, epoch, **kev_aug.KEV_DEFAULTS)
        else:
            out = list(rs)
        main, extra = out[:len(rs)], out[len(rs):]
        for r in main:
            ex = make_example(r, prompt_mod, drop_state)
            ex["prov"]["role"] = "base"
            sib = []
            for e in extra:
                if e["qname"] == r["qname"]:
                    sx = make_example(e, prompt_mod, drop_state)
                    sx["prov"]["role"] = "sibling"
                    sib.append(sx)
            units.append([ex] + sib)
        assert sum(len(u) - 1 for u in units[-len(main):]) == len(extra), "a pair sibling has no base question"
    rng = random.Random(kev_aug.source_seed(seed, f"shuffle:{epoch}"))
    order = list(range(len(units)))
    rng.shuffle(order)
    return [units[i] for i in order]


def build(args):
    prompt_mod = load_prompt_module(args.prompt_dir)
    rows = read_rows(args.train, args.limit)
    os.makedirs(args.out_dir, exist_ok=True)
    manifest = {"script": "build_kev_sft.py", "args": vars(args), "prompt_version": prompt_mod.PROMPT_VERSION,
                "input": {"path": args.train, "sha256": file_sha256(args.train), "rows": len(rows)},
                "code_sha256": {n: file_sha256(os.path.join(HERE, n)) for n in ("build_kev_sft.py", "kev_aug.py")},
                "prompt_py_sha256": file_sha256(os.path.join(args.prompt_dir, "prompt.py")),
                "epochs": {}}
    for ep in range(args.epochs):
        units = epoch_units(rows, args.seed, ep, args.augment, prompt_mod, args.drop_state)
        path = os.path.join(args.out_dir, f"train.e{ep}.jsonl")
        gold_pos, aug_modes, by_source = Counter(), Counter(), Counter()
        n_ex = 0
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for ui, unit in enumerate(units):
                for ex in unit:
                    ex["prov"]["unit"] = ui
                    f.write(json.dumps(ex, ensure_ascii=False, separators=(",", ":")) + "\n")
                    n_ex += 1
                    gold_pos[ex["gold_index"]] += 1
                    by_source[ex["prov"]["source"]] += 1
                    aug_modes[(ex["prov"]["aug"] or {}).get("mode", "none")] += 1
        manifest["epochs"][str(ep)] = {"path": path, "sha256": file_sha256(path), "base_questions": len(units),
                                       "examples": n_ex, "steps_at_10_per_step": -(-len(units) // 10),
                                       "gold_at_position_0": gold_pos[0], "by_aug_mode": dict(sorted(aug_modes.items())),
                                       "by_source": dict(sorted(by_source.items()))}
        print(f"epoch {ep}: {len(units)} base questions, {n_ex} examples -> {path}", flush=True)
    with open(os.path.join(args.out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", default=DEFAULT_TRAIN)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=2, help="prereg §7.2: seed 2")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--augment", choices=("none", "kev"), default="kev")
    ap.add_argument("--drop-state", action="store_true", help="arm K1-QO: remove the input section (prompt.drop_input)")
    ap.add_argument("--limit", type=int, default=0, help="tests/smoke: first N rows only")
    ap.add_argument("--prompt-dir", default=R0_CODE)
    build(ap.parse_args(argv))


if __name__ == "__main__":
    main()
