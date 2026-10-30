#!/usr/bin/env python3
"""Native Kev NPU compatibility probe; original pointer head and serving temperature.

Run outside the downloaded repository with a frozen copy supplied as --kev-code.
This is an engineering probe on development records, not a test benchmark.
"""
import argparse
import fcntl
import threading
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    for name in ("kev-code", "checkpoint", "base", "suite", "out"):
        ap.add_argument("--" + name, required=True)
    ap.add_argument("--records", type=int, default=4)
    ap.add_argument("--base-id", required=True)
    ap.add_argument("--physical-chip", required=True, type=int)
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()
    if not 1 <= a.records <= 8:
        raise ValueError("Probe permits 1–8 development records only")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lock = (out / "driver.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    frozen = json.loads(Path(a.manifest).read_text())
    for filename, expected in frozen["files"].items():
        if digest(filename) != expected:
            raise ValueError("Frozen file changed: " + filename)
    status = {"stage": "loading", "progress": 0, "total": a.records, "chips": 1}
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(15):
            atomic(out / "STATUS.json", {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **status})
            with (out / "heartbeat.log").open("a") as f:
                f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + " ".join(f"{k}={v}" for k,v in status.items()) + "\n")
    threading.Thread(target=heartbeat, daemon=True).start()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    import torch_npu  # noqa: F401
    torch.npu.set_device("npu:0")
    torch.npu.config.allow_internal_format = False
    torch.npu.conv.allow_hf32 = False
    torch.npu.matmul.allow_hf32 = False
    torch.set_num_threads(8)
    sys.path.insert(0, a.kev_code)
    import kev.predictors as predictors
    from kev.checkpoint import Checkpoint, LoadOptions
    from kev.suite import load_split, read_manifest
    from kev.benchmark import prediction_rows

    ck = Checkpoint(a.checkpoint)
    original_base = ck.meta.base
    original_revision = ck.meta.base_revision
    if original_base != a.base_id:
        raise ValueError("Checkpoint base does not match requested identity")
    if Path(a.base, ".complete").read_text().splitlines()[0] != original_revision:
        raise ValueError("Local base revision mismatch")
    # Resolve the same mirrored base locally; no tensor or tokenizer changes.
    ck.meta.base, ck.meta.base_revision = a.base, None
    predictors.Checkpoint = lambda _: ck
    predictors.sync = lambda _: torch.npu.synchronize()
    manifest = read_manifest(a.suite)
    records = load_split(a.suite, "development")[:a.records]
    inputs = [Path(p) for p in frozen["files"]]
    provenance = {"kind": "native_kev_development_probe", "base": original_base,
                  "base_revision": original_revision, "records": a.records,
                  "dtype": "float32", "attention": "eager", "merge": True,
                  "gdn": "transformers_reference", "chips": 1, "physical_chip": a.physical_chip,
                  "files": {str(p): digest(p) for p in inputs}}
    stamp = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    provenance["stamp"] = stamp
    previous = out / "PROVENANCE.json"
    if previous.exists() and json.loads(previous.read_text()) != provenance:
        raise ValueError("Refusing resume with changed provenance")
    atomic(previous, provenance)
    loading_started = time.monotonic()
    predictor = predictors.LocalPredictor(a.checkpoint, "npu:0", LoadOptions(dtype=torch.float32, attn="eager", merge=True), context=manifest["context"])
    load_seconds = time.monotonic() - loading_started
    results = []
    status["stage"] = "development"
    for i, record in enumerate(records):
        target = out / f"record-{i:04d}.json"
        if target.exists():
            envelope = json.loads(target.read_text())
            saved = envelope["payload"]
            checksum = hashlib.sha256(json.dumps(saved, sort_keys=True, allow_nan=False).encode()).hexdigest()
            if envelope["sha256"] != checksum:
                raise ValueError("Changed saved prediction")
            if saved["stamp"] != stamp or saved["record_id"] != record["_meta"]["id"]:
                raise ValueError("Invalid record resume provenance")
            prediction_rows(record, saved["prediction"])
            results.append(saved)
            status["progress"] = i+1
            continue
        started = time.monotonic()
        first = predictor(record)
        first_seconds = time.monotonic() - started
        second_started = time.monotonic()
        second = predictor(record)
        second_seconds = time.monotonic() - second_started
        # Upstream validation checks option coverage, finiteness and simplex.
        rows = prediction_rows(record, first)
        prediction_rows(record, second)
        delta = max(abs(v - second["probabilities"][q][k]) for q, probs in first["probabilities"].items() for k, v in probs.items())
        elapsed = time.monotonic() - started
        result = {"stamp": stamp, "record_id": record["_meta"]["id"], "prediction": first,
                  "question_count": len(rows), "repeat_max_abs_probability_delta": delta,
                  "elapsed_seconds_two_passes": elapsed, "first_pass_seconds": first_seconds,
                  "repeat_pass_seconds": second_seconds, "repeat_questions_per_second_per_chip": len(rows)/second_seconds, "chips": 1,
                  "questions_per_second_per_chip": 2 * len(rows) / elapsed,
                  "reserved_memory_gib": torch.npu.memory_reserved() / 2**30}
        atomic(target, {"payload": result, "sha256": hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()})
        status.update(progress=i+1, questions_per_second_per_chip=result["questions_per_second_per_chip"], reserved_gib=result["reserved_memory_gib"])
        results.append(result)
        with open(out / "heartbeat.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} progress={i+1}/{len(records)} chips=1 questions_per_second_per_chip={result['questions_per_second_per_chip']:.6f} reserved_gib={result['reserved_memory_gib']:.3f}\n")
    atomic(out / "report.json", {"kind": "engineering_development_probe", "run_of_record": False,
           "test_metrics": False, "records": len(results), "model_environment": predictor.environment,
           "temperature": predictor.temperature, "results": results, "load_seconds": load_seconds,
           "base_id": original_base, "base_revision": original_revision, "physical_chip": a.physical_chip, "chips": 1,
           "verdict": "Compatibility executed; throughput and numeric repeatability require review before full evaluation"})
    for filename, expected in frozen["files"].items():
        if digest(filename) != expected:
            raise ValueError("Frozen file changed during probe: " + filename)
    stop.set()
    status["stage"] = "complete"
    atomic(out / "STATUS.json", status)
    atomic(out / "REFERENCE_PROBE_COMPLETE.json", {"rc": 0, "stamp": stamp, "records": len(results), "test_metrics": False})


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        if "--out" in sys.argv:
            out = Path(sys.argv[sys.argv.index("--out")+1])
            out.mkdir(parents=True, exist_ok=True)
            atomic(out / "REFERENCE_PROBE_COMPLETE.json", {"rc": 1, "error": str(exc), "test_metrics": False})
        raise
