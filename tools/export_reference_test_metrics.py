#!/usr/bin/env python3
"""Export existing upstream Kev test summaries without inference or item access.

Reads only runs/locked/*/summary.json, runs/**/report.json, suite manifests,
release asset specifications and docs/claims.json. No prediction rows or test
items are opened. Historical candidates remain separate from released models.
Usage: python3 -I tools/export_reference_test_metrics.py --repo DIR --out DIR
"""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


METRIC_BLOCKS = (
    "clean", "calibrated_clean", "tasks", "variants", "heldout_tasks",
    "paired_flip", "permutation", "coverage", "latency_ms", "unknowable",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pointer(parts):
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def leaves(value, parts=(), counts=None, method=None):
    """Keep counts as context, not an invented metric-specific denominator."""
    counts = dict(counts or {})
    if isinstance(value, dict):
        for key in ("n", "pairs", "units"):
            if key in value:
                counts[key] = {"value": value[key], "path": pointer(parts + (key,))}
        method = value.get("metric", method)
        for key, child in value.items():
            yield from leaves(child, parts + (key,), counts, method)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from leaves(child, parts + (i,), counts, method)
    elif value is None or (isinstance(value, (int, float)) and not isinstance(value, bool)):
        yield parts, value, counts, method


def export(repo, out):
    repo = repo.resolve()
    claims_path = repo / "docs/claims.json"
    claims = read_json(claims_path) if claims_path.exists() else []
    claims_by_source = {}
    for claim in claims:
        claims_by_source.setdefault(claim.get("source"), []).append(claim)

    manifests = {}
    for path in sorted((repo / "evals").rglob("manifest.json")):
        manifests.setdefault(sha256(path), []).append(str(path.relative_to(repo)))

    releases = {}
    for path in sorted((repo / "docs/releases").glob("*-assets.json")):
        data = read_json(path)
        for asset in data.get("assets", []):
            if asset.get("locked"):
                releases.setdefault(asset["locked"], []).append({
                    "spec": str(path.relative_to(repo)), "spec_sha256": sha256(path),
                    "release": data.get("release"), "asset": asset,
                })

    paths = sorted((repo / "runs/locked").glob("*/summary.json"))
    skipped = Counter()
    for path in sorted((repo / "runs").rglob("report.json")):
        data = read_json(path)
        if data.get("split") == "test":
            paths.append(path)
        else:
            skipped[str(data.get("split", "unspecified"))] += 1

    artifacts, rows = [], []
    for path in paths:
        data = read_json(path)
        rel = str(path.relative_to(repo))
        locked = rel.startswith("runs/locked/") and path.name == "summary.json"
        if not locked and data.get("split") != "test":
            raise ValueError(f"Refusing non-test artifact: {rel}")
        if locked and data.get("split") not in (None, "test"):
            raise ValueError(f"Conflicting split in locked artifact: {rel}")
        sha = sha256(path)
        source_claims = claims_by_source.get(rel, [])
        artifact = {
            "path": rel, "sha256": sha,
            "evidence_kind": "upstream_reported_not_locally_reproduced",
            "split": "test",
            "split_evidence": "upstream runs/locked convention; scripts/build_release_assets.py"
                if locked else "explicit report.split == test",
            "release_assets": releases.get(rel, []),
            "claims": source_claims, "original_summary": data,
        }
        artifacts.append(artifact)
        if locked:
            panels = [(name, panel, ("suites", name), data.get("trial"))
                      for name, panel in data["suites"].items()]
        elif "systems" in data:
            panels = [(name, panel, ("systems", name), data.get("sources", {}).get(name, {}).get("run"))
                      for name, panel in data["systems"].items()]
        else:
            panels = [("report", data, (), data.get("run"))]
        for panel_name, panel, prefix, model in panels:
            suite_hash = panel.get("suite_sha256", data.get("suite_sha256", data.get("suite_manifest_sha256")))
            suite = panel.get("suite", data.get("suite"))
            suite_manifests = manifests.get(suite_hash, [])
            if not suite and len(suite_manifests) == 1:
                suite = str(Path(suite_manifests[0]).parent)
            blocks = ("datasets", "areas", "overall") if "systems" in data else METRIC_BLOCKS
            for block in blocks:
                if block not in panel:
                    continue
                for parts, value, counts, method in leaves(panel[block], prefix + (block,)):
                    metric_path = pointer(parts)
                    matched = [c for c in source_claims if pointer(tuple(c.get("path", []))) == metric_path]
                    local_parts = parts[len(prefix):]
                    source = str(local_parts[1]) if block in ("tasks", "datasets", "areas", "heldout_tasks") and len(local_parts) > 1 else None
                    variant = str(local_parts[1]) if block == "variants" and len(local_parts) > 1 else ("clean" if block in ("clean", "calibrated_clean", "tasks") else None)
                    rows.append({
                        "artifact": rel, "artifact_sha256": sha, "split": "test",
                        "panel": panel_name, "suite": suite, "suite_sha256": suite_hash,
                        "suite_manifests": suite_manifests, "model_or_trial": model,
                        "release_assets": releases.get(rel, []),
                        "upstream_git_commit": data.get("git_commit"),
                        "trial_result_sha256": data.get("trial_result_sha256"),
                        "temperature": data.get("temperature"),
                        "source": source, "variant": variant, "block": block,
                        "metric": str(parts[-1]), "metric_path": metric_path,
                        "value": value, "count_context": counts,
                        "declared_metric": method,
                        "metric_policy": data.get("metric_policy"),
                        "formula": data.get("formula"),
                        "published_claims": matched,
                    })

    if not rows:
        raise ValueError("No test metrics found; refusing empty success")
    result = {
        "schema_version": 1, "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_repo": str(repo), "claims_sha256": sha256(claims_path) if claims_path.exists() else None,
        "scope": "Existing upstream test summaries only; no inference, test-item or prediction-row access",
        "count_context_note": "Nearest enclosing n/pairs/units are preserved with paths; they are not asserted as the denominator of every nested metric.",
        "version_note": "Historical candidates, release asset revisions, raw/calibrated metrics and aggregate reports remain distinct; no cross-artifact averaging or winner selection.",
        "skipped_reports_by_split": dict(skipped), "artifact_count": len(artifacts),
        "metric_count": len(rows), "artifacts": artifacts, "metrics": rows,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "kev_test_metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index = {key: value for key, value in result.items() if key not in ("artifacts", "metrics")}
    index["artifacts"] = [{key: value for key, value in artifact.items() if key != "original_summary"}
                          for artifact in artifacts]
    (out / "kev_test_artifact_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "kev_test_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    print(json.dumps({"artifact_count": len(artifacts), "metric_count": len(rows),
                      "skipped_reports_by_split": dict(skipped), "out": str(out)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    export(args.repo, args.out)
