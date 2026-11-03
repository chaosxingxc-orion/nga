#!/usr/bin/env python3
"""Prospective CPU-testable native inference shard runner.

This module deliberately does not load a model or claim an NPU reservation.  It
implements the file/lifecycle contract a future host runner can call: immutable
population pins, global ordinals, item-level COMMITTED records, resumability,
and a bounded operational log.  A real model adapter is supplied by the host.
"""
import argparse
import fcntl
import math
import traceback
import hashlib
import json
import os
import time
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":"), ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def strict_loads(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    require(type(value) is dict, "JSON object required")
    def finite(node):
        if type(node) is float:
            require(math.isfinite(node), "nonfinite JSON")
        elif type(node) is dict:
            for child in node.values(): finite(child)
        elif type(node) is list:
            for child in node: finite(child)
    finite(value)
    return value


def read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    require(len(raw) <= 4 * 1024 * 1024, "JSON exceeds bounded size")
    return strict_loads(raw)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    with pending.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, ensure_ascii=False,
                  allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def _safe_ref(ref):
    require(isinstance(ref, dict) and set(ref) == {"path", "sha256"},
            "reference fields differ")
    path = Path(ref["path"])
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
            "reference path must be absolute and non-symlink")
    require(file_sha(path) == ref["sha256"], "reference bytes changed")
    return path


def load_population(population_ref, shard_id):
    """Authenticate fixed population bytes and its actual parent/input sources."""
    from tools import bev_native_shard_contract as S
    population_path = _safe_ref(population_ref)
    population = read_json(population_path)
    binding = S.validate(population)
    require(type(shard_id) is int and shard_id in (0, 1), "shard id differs")
    parent = read_json(_safe_ref(binding["parent_population"]))
    require(parent.get("schema") == "bev-native-panel-host-v1"
            and parent.get("scope") == "public_fixed_base_test", "parent population scope differs")
    for k in ("scientific_acceptance", "candidate_test_authority", "candidate_selection_allowed"):
        require(parent.get(k) is False, "parent authority differs")
    require(type(parent.get("batch_size")) is int and parent["batch_size"] == 1
            and parent.get("max_length") == 8192 and parent.get("adapter") is None,
            "parent numerical source differs")
    for k, p in (("inputs", "inputs"), ("model_sha256", "model_sha256"),
                 ("contract_sha256", "contract_sha256"),
                 ("source_protocol_binding_sha256", "protocol_binding_sha256"),
                 ("global_count", "count"), ("ordered_inputs_sha256", "ordered_inputs_sha256")):
        require(binding[k] == parent[p] and type(binding[k]) is type(parent[p]), "parent binding differs")
    require(digest(parent["model_files"]) == parent["model_sha256"], "parent model inventory differs")
    # This verifies pinned source references, not current model disk bytes or an
    # execution permission. The future host owns those separate gates.
    return population, binding, population["shards"][shard_id], population_path


def load_requests(binding):
    path = _safe_ref(binding["inputs"])
    rows = []
    with path.open(encoding="utf-8") as stream:
        for ordinal, line in enumerate(stream):
            require(line.endswith("\n") and line.strip(), "torn request row")
            row = strict_loads(line)
            require(type(row.get("i")) is int and row["i"] == ordinal,
                    "request global ordinal differs")
            require("y" not in row and "gold" not in row, "gold in inference request")
            ids = row.get("input_ids")
            require(type(ids) is list and 0 < len(ids) <= 8192
                    and all(type(x) is int and x >= 0 for x in ids), "invalid input tokens")
            rows.append(row)
    require(len(rows) == binding["global_count"], "request population count differs")
    require(digest(rows) == binding["ordered_inputs_sha256"], "ordered input identity differs")
    # Recompute the same canonical ordered identity used by the builder.
    canonical = []
    for ordinal, row in enumerate(rows):
        canonical.append({"i": ordinal, "qid": row["qid"],
                          "request_sha256": row["request_sha256"],
                          "input_sha256": digest(row)})
    require(digest(canonical) == binding["global_request_identities_sha256"],
            "request identity population changed")
    return rows


def _record_identity(request, prediction, ordinal, model_sha256, contract_sha256):
    require(type(prediction) is dict and "y" not in prediction and "gold" not in prediction,
            "prediction contains gold")
    require(type(prediction.get("i")) is int and prediction["i"] == ordinal and prediction.get("qid") == request["qid"],
            "prediction identity differs")
    require(prediction.get("request_sha256") == request["request_sha256"],
            "prediction request binding differs")
    require(prediction.get("input_sha256") == digest(request), "prediction prepared input differs")
    require(prediction.get("contract_sha256") == contract_sha256, "prediction contract differs")
    return {"schema": "bev-native-shard-item-v1", "i": ordinal,
            "qid": request["qid"], "request_sha256": request["request_sha256"],
            "input_sha256": digest(request),
            "model_sha256": model_sha256, "contract_sha256": contract_sha256,
            "prediction": prediction}


def _load_item(path, request, ordinal, model_sha256, contract_sha256):
    require(not any(p.is_symlink() for p in (Path(path), *Path(path).parents)), "unsafe item path")
    record_path = Path(path) / "record.json"
    commit_path = Path(path) / "COMMITTED.json"
    require(not record_path.is_symlink() and not commit_path.is_symlink(), "unsafe record link")
    require(record_path.is_file() and commit_path.is_file(), "partial item record")
    commit = read_json(commit_path)
    require(set(commit) == {"record_sha256", "i", "shard_id"}
            and type(commit.get("i")) is int and commit["i"] == ordinal, "commit identity differs")
    require(commit.get("record_sha256") == file_sha(record_path), "item commit hash differs")
    record = read_json(record_path)
    require(record.get("schema") == "bev-native-shard-item-v1"
            and record.get("i") == ordinal
            and record.get("model_sha256") == model_sha256
            and record.get("contract_sha256") == contract_sha256,
            "item record binding differs")
    expected = _record_identity(request, record["prediction"], ordinal, model_sha256, contract_sha256)
    require(digest(record) == digest(expected), "record fields differ")
    return record["prediction"]


def _run_locked(population_ref, shard_id, output, predictor, validator, *, attempt=1, metadata=lambda: {}):
    """Run a resumable shard using a caller-owned model adapter.

    ``predictor(request)`` must return a prediction carrying the request identity;
    this function never receives labels and never computes accuracy.  The return
    value and ``EXIT.json`` are operational only (scientific acceptance remains
    false). Handled failures can resume in a new attempt: committed items are
    revalidated and reused. Abrupt death without EXIT requires host reconciliation.
    """
    require(type(attempt) is int and attempt >= 1, "attempt must be positive exact integer")
    population, binding, shard, population_path = load_population(population_ref, shard_id)
    requests = load_requests(binding)
    identities = [{"i": i, "qid": r["qid"], "request_sha256": r["request_sha256"],
                   "input_sha256": digest(r)} for i, r in enumerate(requests)]
    for manifest in population["shards"]:
        require(digest([identities[i] for i in manifest["global_ordinals"]])
                == manifest["assigned_request_identities_sha256"], "assigned request hash differs")
    output = Path(output)
    attempt_root = output / "attempts" / str(attempt)
    items_root = output / "items"
    require(not (output / "attempts").is_symlink() and not items_root.is_symlink(), "unsafe attempt/items path")
    for previous in range(1, attempt):
        terminal = read_json(output / "attempts" / str(previous) / "EXIT.json")
        require(type(terminal.get("exit_code")) is int and terminal["exit_code"] != 0
                and type(terminal.get("attempt")) is int and terminal["attempt"] == previous
                and type(terminal.get("shard_id")) is int and terminal["shard_id"] == shard_id
                and terminal.get("scientific_acceptance") is False
                and terminal.get("execution_authorized") is False
                and terminal.get("generation_sha256") == digest({"population": population_ref, "shard_id": shard_id}),
                "prior attempt identity/scope differs or not failed; reconcile first")
    items_root.mkdir(exist_ok=True)
    assigned_names = {f"{i:06d}" for i in shard["global_ordinals"]}
    require({p.name for p in items_root.iterdir()} <= assigned_names, "foreign item directory")
    require(sum(len(requests[i]["input_ids"]) for i in shard["global_ordinals"])
            == shard["input_tokens"], "shard token accounting differs")
    log_path = attempt_root / "runtime.log"
    model_sha = binding["model_sha256"]
    contract_sha = binding["contract_sha256"]
    started = time.monotonic(); reused = computed = 0

    def log(stage, **fields):
        event = {"utc_seconds": time.time(), "stage": stage,
                 "shard_id": shard_id, "attempt": attempt, **fields}
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def perf():
        source = metadata()
        value = source.get("reserved_gib")
        require(value is None or (type(value) in (int, float) and math.isfinite(value) and value >= 0),
                "invalid reserved memory")
        return {"chips": 1, "reserved_gib": value}

    write_json(attempt_root / "heartbeat.json", {"state": "running", "shard_id": shard_id,
                                                   "attempt": attempt, "utc_seconds": time.time()})
    log("population_validated", global_count=binding["global_count"], assigned_count=shard["assigned_count"],
        population_sha256=file_sha(population_path))
    try:
        log("adapter_ready", adapter="caller_owned_model_readiness_not_verified")
        for offset, ordinal in enumerate(shard["global_ordinals"], 1):
            request = requests[ordinal]
            item_dir = items_root / f"{ordinal:06d}"
            if item_dir.exists():
                prediction = _load_item(item_dir, request, ordinal, model_sha, contract_sha)
                sid = read_json(item_dir / "COMMITTED.json")["shard_id"]
                require(type(sid) is int and sid == shard_id, "commit shard differs")
                validator(prediction, request, binding)
                reused += 1
            else:
                prediction = predictor(request)
                validator(prediction, request, binding)
                record = _record_identity(request, prediction, ordinal, model_sha, contract_sha)
                item_dir.mkdir()
                write_json(item_dir / "record.json", record)
                write_json(item_dir / "COMMITTED.json",
                           {"record_sha256": file_sha(item_dir / "record.json"),
                            "i": ordinal, "shard_id": shard_id})
                _load_item(item_dir, request, ordinal, model_sha, contract_sha)
                computed += 1
            if offset == 1 or offset % 100 == 0 or offset == len(shard["global_ordinals"]):
                elapsed = max(time.monotonic() - started, 1e-9)
                log("progress", completed=offset, total=len(shard["global_ordinals"]),
                    reused=reused, computed=computed,
                    questions_per_second_per_chip=computed / elapsed, **perf())
                write_json(attempt_root / "heartbeat.json",
                           {"state": "running", "completed": offset,
                            "total": len(shard["global_ordinals"]), "shard_id": shard_id,
                            "attempt": attempt, "utc_seconds": time.time()})
        if reused:
            log("resume", reused=reused, computed=computed)
        result = {"schema": "bev-native-shard-result-v1", "shard_id": shard_id,
                  "attempt": attempt, "assigned_count": len(shard["global_ordinals"]),
                  "computed": computed, "reused": reused,
                  "model_sha256": model_sha, "contract_sha256": contract_sha,
                  "manifest_sha256": digest(shard), "exit_code": 0,
                  "scientific_acceptance": False, "execution_authorized": False}
        write_json(attempt_root / "report.json", result)
        log("complete", completed=result["assigned_count"], reused=reused, computed=computed)
        write_json(attempt_root / "EXIT.json", {"exit_code": 0, "attempt": attempt,
                                                  "shard_id": shard_id,
                                                  "scientific_acceptance": False,
                                                  "execution_authorized": False,
                                                  "generation_sha256": digest({"population": population_ref, "shard_id": shard_id}),
                                                  "utc_seconds": time.time()})
        return result
    except BaseException as exc:
        # Avoid logging exception text, which may contain input data or secrets.
        frames = [{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                  for f in traceback.extract_tb(exc.__traceback__)[-12:]]
        log("failure", error_type=type(exc).__name__, traceback_frames=frames)
        write_json(attempt_root / "EXIT.json", {"exit_code": 1, "attempt": attempt,
                                                  "shard_id": shard_id,
                                                  "scientific_acceptance": False,
                                                  "execution_authorized": False,
                                                  "generation_sha256": digest({"population": population_ref, "shard_id": shard_id}),
                                                  "utc_seconds": time.time()})
        raise


def run_shard(population_ref, shard_id, output, predictor, validator, *, attempt=1, metadata=lambda: {}):
    """CPU-testable execution core; caller supplies independently bound arithmetic validator.

    No NPU/model loading, launch permission or numerical equivalence is implied.
    """
    output = Path(output)
    require(output.is_absolute() and not any(p.is_symlink() for p in (output, *output.parents)),
            "unsafe output path")
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / "runner.lock").is_symlink() and not (output / "IDENTITY.json").is_symlink(),
            "unsafe control path")
    with (output / "runner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Only safe destination and concurrency checks precede this envelope.
        # Invalid paths or an active writer cannot safely receive failure files.
        require(type(attempt) is int and attempt >= 1, "attempt must be positive exact integer")
        require(type(shard_id) is int and shard_id in (0, 1), "shard id differs")
        attempts = output / "attempts"
        require(not attempts.is_symlink(), "unsafe attempts path")
        attempt_root = attempts / str(attempt)
        require(not attempt_root.exists() and not attempt_root.is_symlink(),
                "attempt already exists; reconcile first")
        attempt_root.mkdir(parents=True)
        identity = {"population": population_ref, "shard_id": shard_id}
        generation = digest(identity)
        log_path = attempt_root / "runtime.log"
        def event(stage, **fields):
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"utc_seconds": time.time(), "stage": stage,
                                         "attempt": attempt, "shard_id": shard_id,
                                         "generation_sha256": generation, **fields},
                                        allow_nan=False, sort_keys=True) + "\n")
                stream.flush(); os.fsync(stream.fileno())
        event("startup")
        write_json(attempt_root / "heartbeat.json", {"state": "created", "attempt": attempt,
                    "shard_id": shard_id, "utc_seconds": time.time()})
        try:
            identity_path = output / "IDENTITY.json"
            if identity_path.exists():
                require(digest(read_json(identity_path)) == generation, "output generation differs")
            else:
                write_json(identity_path, identity)
            return _run_locked(population_ref, shard_id, output, predictor, validator,
                               attempt=attempt, metadata=metadata)
        except BaseException as exc:
            if not (attempt_root / "EXIT.json").exists():
                frames = [{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                          for f in traceback.extract_tb(exc.__traceback__)[-12:]]
                event("startup_failure", error_type=type(exc).__name__, traceback_frames=frames)
                write_json(attempt_root / "EXIT.json", {"exit_code": 1, "attempt": attempt,
                           "shard_id": shard_id, "generation_sha256": generation,
                           "scientific_acceptance": False, "execution_authorized": False,
                           "utc_seconds": time.time()})
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--population", required=True)
    parser.add_argument("--shard", required=True, type=int)
    parser.add_argument("--output", required=True)
    parser.parse_args()
    raise SystemExit("A model predictor is required; this CLI is intentionally non-executable")


if __name__ == "__main__":
    main()
