# Unified CPU pipeline v1

This callable composition processes one already completed host handoff under explicit operator authorization. It does not dispatch new host work, change the DAG, claim NPU capacity, or confer scientific acceptance. The consumer remains responsible for host and receipt authentication and uses the existing shared CPU controller and slot count. Event-service correctness and real Docker execution require independent review.

Provision private persistent directories and protect every input, output, controller, and state directory against untrusted writers. The caller supplies a pinned JSON config with exactly these fields:

```json
{
  "schema": "unified-cpu-pipeline-v1",
  "authorization": "existing-completed-host-event-cpu-processing",
  "event": {"path": "/absolute/handoff.json", "sha256": "<sha256>"},
  "host_config": {"path": "/absolute/host.json", "sha256": "<sha256>"},
  "image": "sha256:<64 lowercase hex>",
  "image_env": [],
  "template": {"path": "/absolute/template.json", "sha256": "<sha256>"},
  "inputs": [{"source": "/absolute/host-output", "target": "/run/nga/output"}],
  "export_output": "/absolute/existing-export-directory",
  "score_output": "/absolute/existing-score-directory",
  "controller": "/absolute/shared-cpu-controller",
  "slots": 1,
  "state_dir": "/absolute/private-pipeline-state"
}
```

`inputs` must declare individual read-only mounts at their original paths for the source config, panel manifest, model directory (including `/model/...` when that is the configured path), model manifest, dataset, panel contract, and population contract, items, gold and requests. The source output uses the fixed `/run/nga/output` mount. Targets are restricted to exactly these dependencies; individual data files must be regular non-executable files and model inventory entries must be regular non-executable files or directories. No broad data-directory, code, or device mount is accepted. All configured paths remain unchanged. The host config and source output must match the authenticated handoff. The image environment must match the image's inspected environment. Consumer path and mount restrictions apply.

The pinned template has exactly `schema`, `export`, and `score`. Its schema is `unified-cpu-pipeline-template-v1`. `export` is the complete closed `native-panel-export-v2` task: `schema`, `adapter`, `runtime`, `source`, `owner_sha256`, `source_config`, `source_config_sha256`, `panel_manifest`, `panel_manifest_sha256`, and `output`. `source` is `/run/nga/output/result`, `output` is `/run/nga/export/result`, and the schema and runtime are `nga-unified-config-v1` and `cpu`. The immutable `score` object has integer `workers` in 1–32 and `chunk_size` in 1–1024. Before export, the pipeline resolves and hashes declared dependencies and verifies model inventory; the adapter performs its own content and inference-owner admission after create. The pipeline derives individual score mounts for the four original population files and validates the exported manifest against its pinned original before scoring. No command or adapter is configurable.

Call `run(config_pin)` for future daemon composition. It takes a lifetime lock, records its identity and source bytes, persists deterministic tasks, consumer configurations and stage pin records atomically before each consumer effect, and refuses changes on recovery. It validates export ancestry and retained record inventory, then checks score consumer ancestry and scorer OWNER, report and EXIT against the exact task, manifest and summary before publishing a terminal, including after a score ACK crash. Reuse rechecks these artifacts. `TERMINAL.json` binds these receipts; physical completion and internal consistency are not numerical or scientific acceptance. Errors propagate without a success terminal. Do not delete retained consumer containers or alter stage artifacts during recovery.

Example detached relaunch (replace all placeholders, use a persistent filesystem and an external supervisor; the config and its pin remain identical on every relaunch):

```sh
nohup /absolute/python3 -B -P /absolute/nga/tools/unified_cpu_pipeline_v1.py --config /absolute/pipeline.json --sha256 '<config-sha256>' >> /absolute/private-pipeline-state/worker.log 2>&1 < /dev/null &
```

The terminal file is the success source of truth. A missing terminal means incomplete or uncertain, not necessarily that no container was created. The caller must establish authority for the complete executable closure *before launch*: reviewed pipeline, consumer, resource lease and schema; the Python interpreter, standard library, jsonschema and its dependencies; Docker client, daemon and inspected image environment; and immutable image ID and provenance covering entrypoint, adapter, inference admission, scorer, all imported native sources and libraries. The recorded source hashes only detect drift relative to the first run; freshly computed hashes do not approve code. Deliver reviewed source and image pins through a trusted deployment process and protect loaded code, imports, configs, inputs, outputs and state against concurrent writers for the entire run and retention period. The namespace test uses host interpreter and repository code and is not a hermetic image qualification. Locks assume reliable flock, fsync and atomic replacement; coherent rewriting of the entire trusted chain is outside this corruption-detection boundary. External supervision and storage protection are required. The engineering HOLD remains in effect.
