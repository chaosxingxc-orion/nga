# Unified resource provider v1 — component under review

This standalone observer produces the exact `nga-dag-observation-v1` and a separate provenance receipt. It does not claim, start, stop, dispatch, or authorize a lease. The event service still uses its unknown provider; integration is a separate task. Final admission remains the existing host/lease lock-held check. This is not a production queue qualification.

The pinned JSON config has exactly these fields:

```json
{
  "schema": "unified-resource-provider-config-v1",
  "allocation": "/absolute/existing/allocation.json",
  "evidence_roots": ["/absolute/registered/evidence/root"],
  "host_configs": [{"path": "/absolute/host.json", "sha256": "64 lowercase hex digits"}],
  "historical_releases": [],
  "allowed_device_ids": [0, 1, 2, 3],
  "max_age_seconds": 30
}
```

Each pinned host config must pass the existing host and lease validation and specify exactly its fixed 1, 2, or 4 devices. The allocation lock must already exist. Each optional historical release is `{"host_config": HOST_PIN, "free_entry": RELEASED_ENTRY, "refs": {"claim": PIN, "release": PIN, "container": PIN_OR_NULL, "terminal": PIN_OR_NULL}}`; it is checked using the real predecessor verifier and the retained container identity, without treating a current successor as a historical conflict. Current ledger ownership still reports busy. The host config must be registered and the release located beneath a registered root. Unknown and absent entries never become free. Nonempty or missing pending claims prevent free observations.

The fixed physical probe is `/usr/local/sbin/npu-smi info -t proc-mem -i CHIP`, on physical `k8s-node1` only, with the strict single-chip 175 response grammar. Docker inventory uses one full listing and batched inspect. The standard auxiliary profile is accepted only when `/dev/davinci_manager`, `/dev/devmm_svm`, and `/dev/hisi_hdc` are present with exact self mappings, `rwm` grants, and at least one exact `/dev/davinci0`–`/dev/davinci7` mapping; its per-device mappings are accounted to the corresponding chips. A manager node by itself, a broad `/dev` or Ascend mapping, a privileged or cgroup grant, a malformed grant, or any unqualified auxiliary profile conservatively blocks all eight lanes. Explicit `npu-smi` results are checked for each device. This observation is time-bounded and is not atomic with external activity; the host must recheck. The receipt includes raw allocation bytes as hex, digest, boot ID, monotonic interval, lineage pins, owner diagnostics and reasons. Receipts can contain operational paths and ledger contents; protect the evidence directory appropriately.

Owner diagnostics run only after the same physical host check, per-device probe, and batched Docker inventory have succeeded. They reuse that inventory and cache each image identity/environment query; they have no lifecycle operation. Ledger ownership remains busy when physical or diagnostic observation is uncertain.

Docker inspect and image replies, and the directly read allocation, reject duplicate JSON members at every nesting level. Docker state requires a boolean `Running`; supplied `Paused`, `Restarting`, `Dead`, `OOMKilled`, and `RemovalInProgress` flags must also be booleans. Status and activity flags must agree; `OOMKilled` is a historical flag and may remain true after exit or restart. Removal can overlap running or stopped state and reserves its mappings. Missing optional flags remain compatible with existing fixtures. Image `RepoDigests` must be null, absent, or a list of valid SHA-256 digest references; a registry reference matches an entire list element. Invalid inventory makes unclaimed capacity unknown; invalid image data makes owner diagnostics uncertain while the ledger remains busy.

The terminal freshness and publication checks validate source and lineage pins, the allocation identity and bytes, the graph snapshot, and the complete snapshot/receipt pair before taking final boot, monotonic, and wall-clock samples. Publication fails closed if that final interval exceeds `max_age_seconds`, if the boot changes, or if any final pin or ledger check changes. Locks are nonblocking, and subprocess calls are individually bounded. A future caller still needs an overall execution and publication deadline, including blocking filesystem operations, and must enforce its own stricter service freshness limit.

Run from a controlled Python environment with `jsonschema` installed (the host validator requires it). Outside an Ascend container use a venv with isolated Python:

```sh
/absolute/venv/bin/python -I /absolute/nga/tools/unified_resource_provider_v1.py --config /absolute/provider.json --sha256 CONFIG_SHA256 --graph /absolute/graph.json --graph-sha256 GRAPH_SHA256 --evidence-dir /absolute/existing-parent/new-observation
```

Inside an Ascend container use `-P` instead of `-I`; the physical-host check intentionally prevents that container from asserting capacity. The output directory must not already exist. Stdout pins `snapshot.json` and `receipt.json`; neither grants dispatch. No live 175 qualification has been performed. This component requires review, physical probe qualification, and a separate service integration transaction before any production queue claim.
