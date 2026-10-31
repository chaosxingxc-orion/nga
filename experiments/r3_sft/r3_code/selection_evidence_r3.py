"""Verified selection inputs (R3 sections 8.1, 14.11 items 4 and 17).

Recompute development results from stamped rows and the frozen question population.
Never open a Kev test partition. Report summaries alone are not selection evidence.
"""
import copy
import hashlib
import json
import math
import os
import tempfile

import core_r3 as C
import provenance_r3 as PV
import testlock_r3 as TL


class SelectionRefusal(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise SelectionRefusal(reason)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_population(rows, expected, key_fn):
    """Reject same-count wrong populations, duplicates, and invalid scores/decisions."""
    want = {key_fn(r): r for r in expected}
    have = {r["k"]: r for r in rows}
    require(bool(want) and len(want) == len(expected), "empty or duplicate expected question population")
    require(len(rows) == len(have) and set(have) == set(want),
            "readouts do not equal the expected question population (missing, extra or duplicate keys)")
    for key, source in want.items():
        row = have[key]
        scores = row.get("s")
        require(isinstance(scores, list) and len(scores) == len(source["levels"])
                and all(type(x) in (int, float) and math.isfinite(x) for x in scores),
                f"{key}: malformed or nonfinite candidate scores")
        require(row.get("ids") == C.level_ids(source) and row.get("gold") == (source["gold"] if "kev" in source else source["gold_id"]),
                f"{key}: candidate order or gold differs from the frozen task")
        if "kev" in source:
            require(row.get("gold_index") == C.gold_index(source)
                    and row.get("argmax") == C.argmax_first(scores)
                    and row.get("tie") == C.is_tie(scores), f"{key}: stored decision disagrees with scores/gold")
    return [have[key_fn(r)] for r in expected]


def training_variant(manifest):
    """Seed-independent recipe identity; old manifests use the trainer's defaults.

    Keep unknown arguments conservatively, so a future training option cannot
    silently disappear from the seed-pooling boundary. Operational locations,
    monitoring and interruption controls do not define the training recipe.
    """
    recipe = {
        "epochs": 2, "lr": 1e-4, "lora_r": 16, "lora_alpha": 32,
        "lora_dropout": 0.05, "gdn_impl": "ref", "gdn_ckpt": False,
        "grad_ckpt": False, "micro_tokens": 12000, "k2_impl": "rows",
        "k2_rows": 96, "chunk_overhead": 2000, "full_logits": False,
        "max_len": 4096, "drop_state": False, "symbol_file": None,
        "symbol_n": 6675, "limit_rows": 0, "full_ft": False,
    }
    recipe.update(manifest["args"])
    for field in ("seed", "out", "model_path", "total_steps", "kernel",
                  "device", "save_every", "stop_after", "no_merge",
                  "perf_window", "perf_every", "procs_on_chip", "expect_pairs",
                  "allow_any_lr"):
        recipe.pop(field, None)
    return {
        "schema": 1, "args": recipe,
        "model_path": os.path.realpath(manifest["model_path"]),
        "kernel": manifest["kernel"], "total_steps": manifest["total_steps"],
        "model_revision_file": manifest.get("model_revision_file"),
        "train_sha256": manifest.get("train_file", {}).get("sha256"),
        "code_sha256": manifest.get("code_sha256"),
        "prompt_py_sha256": manifest.get("prompt_py_sha256"),
        "param_dtype": manifest.get("param_dtype"),
        "torch": manifest.get("torch"), "transformers": manifest.get("transformers"),
    }


def train_identity(report):
    """Read seed/arm from the trainer's completed manifest, not an evaluation-directory name."""
    h = report["header"]
    m = h["model"]
    require(m.get("kind") == "lora-adapter-unmerged", "selection requires the unmerged LoRA model of record")
    path = os.path.realpath(m["path"])
    require(os.path.basename(path) == "adapter", "adapter must belong to its recorded training run")
    manifest_path = os.path.join(os.path.dirname(path), "manifest.json")
    manifest = load_json(manifest_path)
    args = manifest["args"]
    seed = args.get("seed")
    require(type(seed) is int, "training manifest has no integer seed")
    arm = h["arm"]
    expected_loss = "k2" if arm == "K2" else "k1"
    require(arm in {"K1", "K2", "K1-PT", "K1-QO", "K1-FLA"}, "unsupported selection arm")
    require(manifest.get("arm") == expected_loss and args.get("arm") == expected_loss,
            "evaluation arm disagrees with the training objective")
    require(bool(args.get("drop_state")) == (arm == "K1-QO"), "question-only training identity mismatch")
    require((manifest.get("kernel") == "fla") == (arm == "K1-FLA"), "kernel control identity mismatch")
    require(os.path.realpath(args["out"]) == os.path.dirname(path), "training output does not own this adapter")
    require(os.path.realpath(manifest["model_path"]) == os.path.realpath(m["base_path"]), "training base path mismatch")
    require(not args.get("symbol_file") and not args.get("full_ft"), "this selector does not admit K3/K4")
    require(manifest.get("kernel") in {"ref", "fla"}, "unadmitted training kernel")
    require(manifest.get("total_steps", 0) > 0
            and manifest.get("summary", {}).get("final_step") == manifest["total_steps"], "training is not complete")
    return {"seed": seed, "arm": arm, "training_manifest": manifest_path,
            "training_manifest_sha256": C.sha256_file(manifest_path), "adapter_path": path,
            "training_variant": training_variant(manifest)}


def readout_directories(run_dir):
    """All manifested readout directories, so provenance cannot ignore an unrelated/missing file."""
    result = []
    for root in (os.path.join(run_dir, "trackk"), os.path.join(run_dir, "trackt")):
        for dp, _, files in os.walk(root):
            if any(f.endswith(".jsonl") for f in files):
                result.append(dp)
    return result


def role_for_path(rel):
    if rel.startswith("trackt/"):
        return "trackt/" + os.path.basename(rel).split("__")[0]
    return rel  # Track K question keys repeat across suites, splits and input modes.


def verify_run(run_dir, report):
    h = report["header"]
    m = h["model"]
    require(not h.get("limit") and not h.get("limit_groups") and not h.get("dry_run_warnings"),
            "partial/dry-run report cannot inform selection")
    require(not PV._scorer_problems(h.get("scorer")), "report does not name the scorer of record")
    # A fresh temporary cache forces content hashing instead of trusting a stale hash cache.
    with tempfile.TemporaryDirectory(prefix="nga-selection-hash-") as cache:
        identity = TL.model_identity(m["base_path"], m["path"] if m["kind"] == "lora-adapter-unmerged" else None, cache)
    require(identity["sha256"] == m["sha256"], "report model differs from the weights on disk")
    rid = load_json(os.path.join(run_dir, "RUN_IDENTITY.json"))
    require(rid.get("arm") == h["arm"] and rid.get("track_t_config") == h.get("track_t_config"),
            "report arm/config differs from RUN_IDENTITY")
    return PV.verify(run_dir, readout_directories(run_dir), identity["sha256"], role_of=role_for_path)


def verify_task_manifest(path, entry):
    """build_tasks.py hashes each serialized JSON line without its trailing LF."""
    digest, count = hashlib.sha256(), 0
    with open(path, "rb") as stream:
        for line in stream:
            require(line.endswith(b"\n") and line != b"\n", "Track T task has malformed line framing")
            digest.update(line[:-1])
            count += 1
    require(digest.hexdigest() == entry["sha256"] and count == entry["records"],
            "Track T input differs from the builder manifest")
    return {"records": count, "builder_sha256": digest.hexdigest(), "file_sha256": C.sha256_file(path)}


def rebuild_track_t(run_dir, config_name, data_root=C.DATA_ROOT, selection_only=False):
    import common as RC
    import track_t_r3 as T
    all_records = []
    manifest = load_json(os.path.join(data_root, "manifest.json"))
    for task in ("T1", "T2", "T3"):
        for source in RC.SOURCE_FILES:
            path = RC.task_path(data_root, task, source)
            if task == "T3" and source != "typed-decisions":
                continue
            verify_task_manifest(path, manifest["tasks"][RC.TASK_DIRS[task]][source])
            all_records.extend(RC.load_records(path))
    config = T.CONFIGS[config_name]
    needed = T.records_needed(all_records, config)
    rdir = os.path.join(run_dir, "trackt", "readouts")
    by_role = {role: [] for role in T.MODEL_ROLES}
    for fn in sorted(os.listdir(rdir)):
        role = fn.split("__")[0]
        if fn.endswith(".jsonl") and role in by_role:
            by_role[role].extend(C.read_jsonl(os.path.join(rdir, fn)))
    for role in by_role:
        stored = validate_population(by_role[role], needed, lambda r: r["key"])
        # Rebuild metadata from the task, so stale grouping/source fields cannot change the metric.
        by_role[role] = [T.make_readout(r, row["s"]) for r, row in zip(needed, stored)]
    by_role.update(T.constant_and_uniform_rows(all_records, needed))
    if selection_only:
        import split as split_rules
        # Retain threshold-fitting rows, but do not compute report-half metrics during selection.
        keep = {r["key"] for r in needed if split_rules.GROUP70.assign(r) == split_rules.TRAIN
                or T.half_of(r["group_id"]) == "selection"}
        by_role = {role: [row for row in rows if row["k"] in keep] for role, rows in by_role.items()}
    return T.build_track_t(by_role, all_records, config, selection_only=selection_only)


def load_selection_report(run_dir, kev_dir=C.KEV_DIR, require_track_t=False, report_half=False):
    import degenerate_r3 as D
    import prechecks_r3 as PC
    report = C.load_report(run_dir)
    tid = train_identity(report)
    provenance = verify_run(run_dir, report)
    train, train_path = C.load_partition("decision-v7", "train", kev_dir=kev_dir)
    expected = {}
    paths = [train_path]
    for suite in C.SUITES:
        rows, path = C.load_partition(suite, "dev", kev_dir=kev_dir)
        expected[suite] = rows
        paths.append(path)
    PC.check_kev_manifest(paths, kev_dir=kev_dir)
    require({s: len(v) for s, v in expected.items()} == {"decision-v7": 1264, "transfer-v4": 656},
            "development question counts differ from the frozen protocol")
    const = D.fit_constant(train)
    out = copy.deepcopy(report)
    clean_keys, correct = [], []
    for suite, rows in expected.items():
        metrics = {}
        for kind in ("clean", "question_only", "empty_input"):
            stored = C.read_jsonl(C.k_readout_path(run_dir, suite, "dev", kind))
            ordered = validate_population(stored, rows, C.kev_key)
            metrics[kind] = C.headline(rows, [x["s"] for x in ordered])
            if kind == "clean":
                clean_keys.extend((suite, x["k"]) for x in ordered)
                correct.extend(int(x["argmax"] == x["gold_index"]) for x in ordered)
        const_scores, _ = D.score_constant(const, rows)
        out["track_k"]["partitions"][suite + "/dev"] = {
            "n": len(rows), "headline": metrics["clean"], "arms": {
                "constant": C.headline(rows, const_scores), "question_only": metrics["question_only"],
                "empty_input": metrics["empty_input"]}}
    if require_track_t:
        require(report["header"].get("track_t_config") == "r3", "selection requires the r3 selection half")
        out["track_t"] = rebuild_track_t(run_dir, "r3", selection_only=not report_half)
    out["selection_evidence"] = {**tid, "provenance": provenance, "keys": clean_keys, "correct": correct}
    return out


def validate_seed_reports(reports, required_seeds=(2, 3), required_arm=None):
    require(len(reports) == len(required_seeds), "expected exactly the registered seed reports")
    evidence = [r.get("selection_evidence", {}) for r in reports]
    require(all(type(e.get("seed")) is int for e in evidence), "verified training seed identity is required")
    require(sorted(e["seed"] for e in evidence) == sorted(required_seeds), "missing, duplicate or wrong training seeds")
    require(len({e.get("adapter_path") for e in evidence}) == len(evidence), "same adapter supplied more than once")
    arms = {e.get("arm") for e in evidence}
    require(len(arms) == 1 and None not in arms, "reports must belong to one arm")
    variants = [e.get("training_variant") for e in evidence]
    require(all(isinstance(v, dict) and v.get("schema") == 1 and v.get("args") for v in variants),
            "verified training variant identity is required; reload legacy reports")
    require(all(v == variants[0] for v in variants[1:]),
            "seed reports use different training variants (model, implementation, recipe or provenance)")
    if required_arm:
        require(arms == {required_arm}, f"decision line requires {required_arm}")


def load_r0_gating(run, expected_execution_sha256=None):
    import r0rescore_verify as RV
    marker = load_json(os.path.join(run, "R0RESCORE_COMPLETE.json"))
    require(type(marker.get("exit_code")) is int and marker["exit_code"] == 0
            and marker.get("run_of_record") is True and not marker.get("limit_groups"),
            "R0 re-score must be complete and of record; smoke is not admissible")
    if os.path.exists(os.path.join(run, 'execution.json')):
        require(expected_execution_sha256 is not None, 'externally pinned R0 execution required')
        require(marker.get('execution_sha256') == expected_execution_sha256, 'R0 marker execution differs')
        require(C.sha256_file(os.path.join(run, 'instruct', 'report.json')) == marker.get('report_sha256'),
                'R0 report differs from completion marker')
        require(C.sha256_file(os.path.join(run, 'R0RESCORE_VERIFIED.json')) == marker.get('verified_sha256'),
                'R0 verification differs from completion marker')
    checked = RV.check(run, expected_execution_sha256=expected_execution_sha256)
    require(not checked["problems"], "R0 re-score verification failed: " + str(checked["problems"]))
    out = os.path.join(run, "instruct")
    block = rebuild_track_t(out, "r0")
    lines = block["decision_lines"]["all"]["B-2"]
    statuses = {v["level_type"]: v["status"] for v in lines if v["source"] == "typed-decisions"}
    require(set(statuses) == {"boolean", "nominal", "ordinal"}, "R0 gating population is incomplete")
    return {"run": os.path.abspath(run), "marker_sha256": C.sha256_file(os.path.join(run, "R0RESCORE_COMPLETE.json")),
            "statuses": statuses, "verification": checked}
