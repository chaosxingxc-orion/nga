#!/usr/bin/env python3
"""Fail-closed validation for the dataset-panel admission contract.

This validator consumes only the machine-readable contract and metadata audit. It
never opens dataset files or candidate TEST rows, and it never launches inference.
A contract is admissible only when every listed panel has a complete, explicit
identity/split/metric/overlap record and is marked ``ready_for_inference``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "dataset-expansion-contract-v2"
AUDIT_SCHEMAS = {
    "dataset-expansion-v3-local-metadata-audit-v1",
    "dataset-expansion-v6-local-metadata-audit-v1",
}
READ_KEYS = ("candidate_test_samples_read", "model_outputs_read", "new_inference", "training_changed")
MAX_REASONS = 64


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"regular JSON file required: {path}")
    try:
        value = json.loads(path.read_text())
    except Exception as exc:  # pragma: no cover - error text is bounded below
        raise ValueError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _false_scope(value: Any, where: str, reasons: list[str]) -> None:
    if not isinstance(value, dict):
        reasons.append(f"{where}: read_scope must be an object")
        return
    for key in READ_KEYS:
        if type(value.get(key)) is not bool or value.get(key) is not False:
            reasons.append(f"{where}.read_scope.{key} must be literal false")


def _hash_present(entry: dict[str, Any]) -> bool:
    return any(isinstance(v, str) and len(v) >= 16 for k, v in entry.items() if k.endswith("_sha256"))


def _split_present(entry: dict[str, Any]) -> bool:
    if isinstance(entry.get("split"), str) and entry["split"]:
        return True
    panels = entry.get("panels")
    if isinstance(panels, list) and panels:
        return all(isinstance(x, dict) and isinstance(x.get("split"), str) and bool(x["split"]) for x in panels)
    # A native panel count alone is not a split contract.
    return False


def _metric_present(entry: dict[str, Any]) -> bool:
    for key in ("metrics", "metric_rule", "native_metric", "native_metrics"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
    panels = entry.get("panels")
    return isinstance(panels, list) and bool(panels) and all(
        isinstance(x, dict) and any(isinstance(x.get(k), (str, list)) and bool(x.get(k)) for k in ("metrics", "metric", "metric_rule"))
        for x in panels
    )


def _overlap_present(entry: dict[str, Any]) -> bool:
    keys = ("source_overlap_audit_status", "source_overlap_status", "overlap_rule", "source_overlap")
    return any(isinstance(entry.get(k), (str, list, dict)) and bool(entry[k]) for k in keys)


def _multimodal(entry: dict[str, Any]) -> bool:
    text = json.dumps(entry, ensure_ascii=False).lower()
    return any(token in text for token in ("image", "video", "multimodal"))


def _multimodal_harness_present(entry: dict[str, Any]) -> bool:
    keys = ("multimodal_harness_status", "multimodal_harness", "harness_status")
    return any(isinstance(entry.get(k), (str, dict)) and bool(entry[k]) for k in keys)


def validate(contract: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if contract.get("schema") != SCHEMA:
        reasons.append(f"contract.schema must be {SCHEMA}")
    if audit.get("schema") not in AUDIT_SCHEMAS:
        reasons.append(f"audit.schema must be one of {sorted(AUDIT_SCHEMAS)}")
    _false_scope(contract.get("read_scope"), "contract", reasons)
    _false_scope(audit.get("read_scope"), "audit", reasons)

    cells = contract.get("candidate_families")
    entries = audit.get("entries")
    if not isinstance(cells, list) or not cells:
        reasons.append("contract.candidate_families must be a non-empty array")
        cells = []
    if not isinstance(entries, list) or not entries:
        reasons.append("audit.entries must be a non-empty array")
        entries = []
    cell_names = {x.get("dataset") for x in cells if isinstance(x, dict) and isinstance(x.get("dataset"), str)}
    entry_names = {x.get("dataset") for x in entries if isinstance(x, dict) and isinstance(x.get("dataset"), str)}
    if cell_names != entry_names:
        reasons.append("contract/audit dataset sets differ")

    ready = 0
    nonready = 0
    for entry in entries:
        if not isinstance(entry, dict):
            reasons.append("audit entry must be an object")
            continue
        name = entry.get("dataset", "<missing dataset>")
        status = entry.get("status")
        if status != "ready_for_inference":
            nonready += 1
            reasons.append(f"{name}: status={status!r}; no FIFO admission")
            continue
        ready += 1
        required = (
            ("identity hash", _hash_present(entry)),
            ("split", _split_present(entry)),
            ("metric rule", _metric_present(entry)),
            ("source overlap status", _overlap_present(entry)),
        )
        for label, ok in required:
            if not ok:
                reasons.append(f"{name}: ready entry missing {label}")
        if _multimodal(entry) and not _multimodal_harness_present(entry):
            reasons.append(f"{name}: ready multimodal entry missing multimodal harness status")

    # The contract itself is authoritative for the requested state; a ready
    # audit entry must agree with its corresponding family declaration.
    by_name = {x.get("dataset"): x for x in cells if isinstance(x, dict)}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("status") != "ready_for_inference":
            continue
        cell = by_name.get(entry.get("dataset"))
        if not cell or cell.get("status") != "ready_for_inference":
            reasons.append(f"{entry.get('dataset', '<missing dataset>')}: contract status disagrees with ready audit")

    reasons = reasons[:MAX_REASONS]
    valid = not reasons and ready == len(entries) and nonready == 0
    return {
        "schema": "dataset-panel-contract-validation-v1",
        "valid": valid,
        "admission": "ready_for_inference" if valid else "NO_FIFO_ADMISSION",
        "contract_schema": contract.get("schema"),
        "audit_schema": audit.get("schema"),
        "counts": {"contract_families": len(cells), "audit_entries": len(entries), "ready": ready, "nonready": nonready, "reasons": len(reasons)},
        "reasons": reasons,
        "read_scope_verified_false": not any("read_scope" in x for x in reasons),
        "candidate_rows_read": False,
        "inference_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate(_load(args.contract), _load(args.audit))
    except ValueError as exc:
        result = {
            "schema": "dataset-panel-contract-validation-v1",
            "valid": False,
            "admission": "NO_FIFO_ADMISSION",
            "counts": {"contract_families": 0, "audit_entries": 0, "ready": 0, "nonready": 0, "reasons": 1},
            "reasons": [str(exc)],
            "candidate_rows_read": False,
            "inference_authorized": False,
        }
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        sys.stdout.write(rendered)
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
