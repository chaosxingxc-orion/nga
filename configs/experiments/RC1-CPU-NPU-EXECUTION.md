# RC1 CPU and NPU execution contract

Owner instruction, 2026-11-06: maximize useful NPU occupancy and keep CPU preparation, scoring, analysis and publication asynchronous. Continue using engineering-base-rc1.

| Plane | Work | Resource rule |
| --- | --- | --- |
| CPU preparation | Resolve configured inputs, reuse accepted data/image/model identities, prepare immutable run configuration and launch prerequisites | Finish before placing the job in the NPU ready queue; acquire no NPU resource |
| NPU execution | Load the prepared model and run configured training or inference | Claim only when the job can execute; release on terminal execution before CPU statistics |
| CPU consumption | Compute scores, compare baselines, inspect cases, review and publish conclusions | Consume saved outputs asynchronously; do not delay unrelated NPU successors |

Keep dependencies only for actual artifact production, physical resource release, or a substantive user decision. Keep pending preparation outside the executable NPU queue. Queue count must distinguish planned, CPU-preparing, NPU-ready, running and terminal jobs. A planned job is not ready work and a running container is not proof of full hardware utilization.

Reuse accepted datasets, image digests and engineering implementation under fixed identities. Do not repeat full dataset, checkpoint or source hashing for every member or polling tick. Complete expensive checks in CPU preparation once per changed input; reuse their bound receipts while inputs remain unchanged. At launch retain the cheap exact-run configuration and live resource ownership checks. Changed inputs invalidate the affected preparation, not every experiment. Do not change evaluation populations, arithmetic or held-out access rules to optimize scheduling.

Current implementation limits: the live host prepares before claiming an NPU, but dispatcher resource waiting currently precedes that preparation, and the model entry repeats shared identity/data checks. A targeted candidate is being developed to move that work ahead of resource waiting and reuse preparation. The current shared twelve-member campaign also waits for all actual identities; this remains a known barrier, not a desired scientific requirement. No claim is made that these pending changes are already deployed.

The operational graph is maintained locally in `.local/releases/engineering-base-rc1/evidence/current-execution/ACTIVE-EXPERIMENT-GRAPH.json`, with explicit CPU and NPU planes. Live monitoring remains script-driven at 600-second cadence or completion events. Publish experiment conclusions on the remote wiki; keep process records local.
