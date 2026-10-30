#!/usr/bin/env python3
"""Convert Kev's frozen suites (jaredpalmer/kev, evals/*; mirrored in jaredpalmer/kev-suites) into our record format.

Run (host, untrusted input is parsed with json only, nothing from it is executed):
    python3 -I convert_kev.py [--suites-dir DIR] [--breadth-dir DIR] [--out DIR]

Input: Kev labelled requests, one JSON object per line,
    {"state": JSONContent, "questions": {qid: {"type": "choice|noul|score", "instructions": JSONContent,
     "criteria": ..., "label": ..., "src": str}}, "_meta": {...}}
Output: one record per (Kev record, question), in file order, question order inside a record preserved:
    {"task": "KEV", "source": "kev-<dataset>", "variant": "original", "group_id", "input", "task_definition",
     "question", "qname", "levels": [{"id","name","definition", "shown"}], "level_type",
     "candidate_set": "exclusive", "gold", "split": "dev|test|train|calibration", "kev": {...provenance...}}

What Kev shows the model (kev/api.py lines 102-117, kev/model.py encode): the state rendered to text by api.render();
per question the instruction text and the options, in dict order, one option per span "<opt> text </opt>". There is NO
task definition, NO option identifier/letter and NO chat template in Kev. The text of an option is
    choice: key                       when the option has no description  (kev/api.py option_text)
            "key: description"        otherwise
    noul:   "no" / "no: desc" , "yes" / "yes: desc"   (options are always [false, true] in that order)
    score:  the level description only (levels have no name; the label is the level index)
Mapping used here (faithful to the text Kev shows):
    level.name       = the identifier part of the option text (choice key; "no"/"yes"; for score the full level text)
    level.definition = the description part, or, where Kev shows only a name, the name itself (counted in the
                       manifest as `definition_fallback_to_name`)
    level.shown      = the exact option text Kev feeds the model; invariant: shown == name when the definition is a
                       fallback, else shown == f"{name}: {definition}"
    level.id         = choice key | "false"/"true" | str(level index) -- the key the gold label is expressed in.
task_definition is not in Kev; the constant TASK_DEFINITION below is ours, recorded in the manifest.

Non-clean variants of Kev (permuted, none_present, none_absent) are NOT headline items (Kev's accuracy is over the
`clean` variant only, kev/benchmark.py summarize) and go to <split>.variants.jsonl with variant = the Kev variant name.
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SUITES_DIR = "/mnt/cephfs/xingchao/datasets/jev/jaredpalmer__kev-suites"
DEFAULT_REPO = "/mnt/cephfs/xingchao/repos/jev/jaredpalmer__kev"
DEFAULT_OUT = "/mnt/cephfs/xingchao/experiments/jev/KEV"

TASK_DEFINITION = "Answer the question about the input using only the options given."
CONVERTER_VERSION = "convert-kev-v1"
LEVEL_TYPE = {"choice": "nominal", "noul": "boolean", "score": "ordinal"}
SPLIT_OF_FILE = {"train": "train", "calibration": "calibration", "development": "dev", "test": "test"}
# suite name -> (path under the suites dir, partitions converted)
SUITES = {
    "decision-v7": ("v7/decision-v7", ("train", "calibration", "development", "test")),
    "transfer-v4": ("v4/transfer-v4", ("development", "test")),   # train / calibration are empty (0 records)
    "breadth-v1": (None, ("development", "test")),                # only via --breadth-dir (not public, see KEV-PROTOCOL.md)
}
META_COPY = ("id", "variant", "parent_id", "pair_id", "pair_kind", "sibling", "none_key", "family", "family_id",
             "render_style", "row", "repo", "revision", "text_sha256")


# ---- Kev's own rendering, copied from kev/api.py (render, option_text, question_keys) -------------------------------
def render(v, indent=0):
    """kev.api.render: flatten str | object | array into the text the model sees."""
    pad = "  " * indent
    if v is None:
        return ""
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    if isinstance(v, list):
        return "\n".join(f"{pad}- {render(x, indent + 1).lstrip()}" for x in v)
    return "\n".join(f"{pad}{k}:\n{render(x, indent + 1)}" if isinstance(x, (dict, list)) else f"{pad}{k}: {render(x)}"
                     for k, x in v.items())


def has_desc(desc):
    return not (desc is None or desc == "")


def option_text(name, desc):
    """kev.api.option_text."""
    return name if not has_desc(desc) else f"{name}: {render(desc)}"


def build_levels(q):
    """-> (levels, gold_id, fallback_count). Mirrors kev.api.to_record option construction and kev.benchmark.labels."""
    t = q["type"]
    levels = []
    if t == "choice":
        for key, desc in q["criteria"].items():
            shown = option_text(key, desc)
            levels.append({"id": key, "name": key, "definition": render(desc) if has_desc(desc) else key, "shown": shown})
        gold = q["label"]
        if not isinstance(gold, str):
            raise ValueError(f"choice label is not a string: {gold!r}")
    elif t == "noul":
        c = q.get("criteria") or {}
        for lid, name in (("false", "no"), ("true", "yes")):
            desc = c.get(lid)
            levels.append({"id": lid, "name": name, "definition": render(desc) if has_desc(desc) else name,
                           "shown": option_text(name, desc)})
        if not isinstance(q["label"], bool):
            raise ValueError(f"noul label is not a bool: {q['label']!r}")
        gold = "true" if q["label"] else "false"
    elif t == "score":
        for i, x in enumerate(q["criteria"]):
            text = render(x)
            levels.append({"id": str(i), "name": text, "definition": text, "shown": text})
        if isinstance(q["label"], bool) or not isinstance(q["label"], int):
            raise ValueError(f"score label is not an int: {q['label']!r}")
        gold = str(q["label"])
    else:
        raise ValueError(f"unknown question type {t!r}")
    fallback = sum(1 for l in levels if l["definition"] == l["name"] and l["shown"] == l["name"])
    return levels, gold, fallback


def convert_record(rec, split, suite, line_no):
    """Yield (our_record, fallback_count, is_clean) for each question of one Kev record, in question order."""
    meta = rec["_meta"]
    n_q = len(rec["questions"])
    state_text = render(rec["state"])
    for qi, (qid, q) in enumerate(rec["questions"].items()):
        levels, gold, fallback = build_levels(q)
        clean = meta["variant"] == "clean"
        kev = {"suite": suite, "line": line_no, "qindex": qi, "questions_in_record": n_q, "qtype": q["type"],
               "src": q["src"], "kev_variant": meta["variant"], "has_target": q.get("target") is not None}
        kev.update({k: meta[k] for k in META_COPY if k in meta})
        out = {"task": "KEV", "source": "kev-" + meta["source"], "variant": "original" if clean else meta["variant"],
               "group_id": meta["group_id"], "input": state_text, "task_definition": TASK_DEFINITION,
               "question": render(q.get("instructions")), "qname": qid, "levels": levels,
               "level_type": LEVEL_TYPE[q["type"]], "candidate_set": "exclusive", "gold": gold, "split": split,
               "kev": kev}
        yield out, fallback, clean


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_kev(path):
    """Yield (line_no, record) for the non-empty lines of a Kev partition (1-based physical line numbers)."""
    with open(path, "r", encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                yield n, json.loads(line)


def convert_partition(src_path, out_dir, suite, kev_file):
    split = SPLIT_OF_FILE[kev_file]
    os.makedirs(out_dir, exist_ok=True)
    main_path = os.path.join(out_dir, f"{split}.jsonl")
    var_path = os.path.join(out_dir, f"{split}.variants.jsonl")
    stats = {"input_records": 0, "input_questions": 0, "clean_records": 0, "clean_questions": 0, "variant_questions": 0,
             "by_source_clean_questions": {}, "by_task_clean_questions": {}, "by_qtype_clean_questions": {},
             "by_variant_questions": {}, "definition_fallback_to_name": {"choice": 0, "noul": 0, "score": 0},
             "levels_total": {"choice": 0, "noul": 0, "score": 0}, "empty_question_text": 0}
    with open(main_path, "w", encoding="utf-8", newline="\n") as fm, open(var_path, "w", encoding="utf-8", newline="\n") as fv:
        for line_no, rec in read_kev(src_path):
            stats["input_records"] += 1
            stats["input_questions"] += len(rec["questions"])
            if rec["_meta"]["variant"] == "clean":
                stats["clean_records"] += 1
            for out, fallback, clean in convert_record(rec, split, suite, line_no):
                qt = out["kev"]["qtype"]
                stats["by_variant_questions"][out["kev"]["kev_variant"]] = stats["by_variant_questions"].get(out["kev"]["kev_variant"], 0) + 1
                if clean:
                    fm.write(dumps(out) + "\n")
                    stats["clean_questions"] += 1
                    for key, val in (("by_source_clean_questions", out["source"]), ("by_task_clean_questions", out["kev"]["src"]),
                                     ("by_qtype_clean_questions", qt)):
                        stats[key][val] = stats[key].get(val, 0) + 1
                    stats["definition_fallback_to_name"][qt] += fallback
                    stats["levels_total"][qt] += len(out["levels"])
                    stats["empty_question_text"] += int(out["question"] == "")
                else:
                    fv.write(dumps(out) + "\n")
                    stats["variant_questions"] += 1
    if stats["variant_questions"] == 0:
        os.remove(var_path)
        var_path = None
    for key in ("by_source_clean_questions", "by_task_clean_questions", "by_qtype_clean_questions", "by_variant_questions"):
        stats[key] = dict(sorted(stats[key].items()))
    stats["outputs"] = {"clean": {"path": os.path.relpath(main_path, out_dir.rsplit("/", 1)[0]), "sha256": file_sha256(main_path),
                                  "rows": stats["clean_questions"]}}
    if var_path:
        stats["outputs"]["variants"] = {"path": os.path.relpath(var_path, out_dir.rsplit("/", 1)[0]),
                                        "sha256": file_sha256(var_path), "rows": stats["variant_questions"]}
    stats["input"] = {"path": src_path, "sha256": file_sha256(src_path)}
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--suites-dir", default=DEFAULT_SUITES_DIR, help="mirror of jaredpalmer/kev-suites")
    ap.add_argument("--repo", default=DEFAULT_REPO, help="clone of jaredpalmer/kev (manifests, commit)")
    ap.add_argument("--breadth-dir", default=None, help="directory holding breadth-v1 development.jsonl / test.jsonl (not public; rebuilt locally)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--suites", default="decision-v7,transfer-v4,breadth-v1")
    a = ap.parse_args(argv)

    manifest = {"converter": CONVERTER_VERSION, "converter_sha256": file_sha256(os.path.abspath(__file__)),
                "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "task_definition": TASK_DEFINITION,
                "kev_suites_dir": a.suites_dir, "suites": {}}
    complete = os.path.join(a.suites_dir, ".complete")
    if os.path.exists(complete):
        manifest["kev_suites_complete"] = json.load(open(complete))
    head = os.path.join(a.repo, ".git", "HEAD")
    if os.path.exists(head):
        import subprocess
        manifest["kev_repo_commit"] = subprocess.run(["git", "-C", a.repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    for suite in a.suites.split(","):
        rel, parts = SUITES[suite]
        if suite == "breadth-v1":
            base = a.breadth_dir
        else:
            base = os.path.join(a.suites_dir, rel)
        entry = {"partitions": {}}
        manifest["suites"][suite] = entry
        if not base or not os.path.isdir(base):
            entry["status"] = "unavailable: partitions are not public (private mirror jaredpalmer/kev-private-evals); pass --breadth-dir"
            continue
        kev_manifest_path = os.path.join(base, "manifest.json")
        if not os.path.exists(kev_manifest_path):   # breadth-v1: only its manifest is public, it is in the repo
            kev_manifest_path = os.path.join(a.repo, "evals", suite, "manifest.json")
        kev_manifest = json.load(open(kev_manifest_path))
        entry["kev_manifest"] = {"path": kev_manifest_path, "sha256": file_sha256(kev_manifest_path)}
        entry["status"] = "converted"
        for kev_file in parts:
            src = os.path.join(base, kev_file + ".jsonl")
            stats = convert_partition(src, os.path.join(a.out, suite), suite, kev_file)
            declared = kev_manifest["files"][kev_file + ".jsonl"]
            stats["kev_manifest_declared"] = {"records": declared["records"], "questions": declared["questions"], "sha256": declared["sha256"]}
            stats["input_matches_kev_manifest"] = (stats["input"]["sha256"] == declared["sha256"] and stats["input_records"] == declared["records"]
                                                   and stats["input_questions"] == declared["questions"])
            entry["partitions"][SPLIT_OF_FILE[kev_file]] = stats
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "manifest.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {path}")
    for suite, entry in manifest["suites"].items():
        for split, st in entry["partitions"].items():
            print(f"{suite:12s} {split:12s} in {st['input_records']:6d} rec / {st['input_questions']:6d} q -> clean {st['clean_questions']:6d}"
                  f" variants {st['variant_questions']:4d}  matches_kev_manifest={st['input_matches_kev_manifest']}")
        if entry["status"] != "converted":
            print(f"{suite:12s} {entry['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
