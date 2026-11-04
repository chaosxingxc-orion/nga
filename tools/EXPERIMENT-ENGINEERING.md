# Experiment execution contracts

These contracts separate functional correctness from engineering efficiency. A code
review, a completed run, an independently accepted result and a scientific decision
are distinct states. This document does not amend experiment metrics or admission.

## Functional baseline first

Freeze the task population, split, model/adapter identity, scoring protocol, thresholds
and output schema before execution. Test successful completion and the failure paths
that could create false success, duplicate computation or invalid resource ownership.
Optimize the accepted path using a new source/configuration generation. Existing runs
keep their frozen dependencies; do not patch an active consumer or overwrite results.

The reusable execution interface consumes configuration. Model paths, input manifests,
output roots, worker counts, chip assignments and process dependencies belong in that
configuration. Bind the concrete implementation and its source hashes at launch. Do
not bake a new experiment identity into a copy of a launcher for every run.

## Reusable nonfunctional requirements

| Requirement | Implementation contract | Acceptance evidence |
| --- | --- | --- |
| NPU utilization | Queue ready, scientifically useful work before the current run completes; represent scientific and resource dependencies separately. | Ready queue depth, per-chip activity and release-to-next-start duration with waiting reason. A running container alone does not prove full utilization. |
| CPU/NPU concurrency | Persist inference output, verify physical release, then dispatch CPU reconstruction and reporting independently. | Real release precedes CPU dispatch; next independent inference does not depend on report formatting. |
| Bounded CPU parallelism | Configure workers/chunk size; bound submitted work; keep per-item state private and deterministic reduction in original order. | Full output and ordered receipt parity, corruption/failure tests and peak resource observations. |
| Numerical equivalence | Reuse frozen arithmetic and input order. Preserve both verification passes where the publication transaction requires them. | Per-record or operand comparisons under the registered tolerance, plus full summary parity. Equal aggregate accuracy alone is insufficient. |
| Survivable execution | Detached retained container, durable Ceph logs, heartbeat, terminal and exact relaunch command. Resume at committed item boundaries. | Disconnect/restart tests and actual retained-container identity; do not restart a successful run. |
| Honest lifecycle | Distinguish prepared, launched, scoring complete, released, CPU complete and accepted. Persist uncertain launches without inventing an exit. | Inject failures before/after spawn and terminal writes; reconcile actual process/container generations. |
| Exclusive ownership | Check claims under resource locks. Fence delayed consumers before a later attempt; compare PID, boot ID and start ticks. | Real-process and cross-process-lock tests; unknown process observations must not mean dead. |
| Portable deployment | Every runtime dependency must be visible on the execution host. Workspace-local review paths are not deployment paths. | Import and configuration verification on host175 using the exact Ceph copy and target interpreter. |
| Low-cost observability | Scripts read heartbeats, logs and terminals; emit bounded summaries and evidence pointers. Use events plus approximately600-second monitoring. | Fresh digest, log error signatures, terminal precedence and explicit observation-unknown state. Agents read only escalated slices. |
| Evidence integrity | Hash immutable input/output evidence; validate committed bytes and source joins. Keep failed generations inspectable. | Frozen source checks, item receipts, independent reconstruction and no overwrite of occupied output. |
| Collaboration | Publish current conclusions and status in place; keep process records local and archive inactive records after three days. | Latest Wiki/table agrees with accepted artifacts; active or pinned paths remain available. |

## Measure the complete cost

For CPU scoring, record inventory verification, imported-record validation, record
scoring and whole-process time. State unmeasured phases rather than forcing phase
times to sum to the whole. Record host, CPU quota, memory limit, worker count,
numerical-library thread limits, source revision and output population.

Report training/inference throughput per chip with chip count and reserved memory.
Keep kernel/scoring time, driver time and claim-to-release time distinct. Report both
latency and total resource cost when comparing single-chip and multi-chip execution.

A single ordered serial/parallel comparison supports a descriptive speed ratio. Cache
warmup, storage metadata load and background contention can affect it. Repeated or
counterbalanced measurements are needed before claiming a stable production speedup.
Saved-readout CPU replay does not measure NPU inference speed or training gains.

## Implementations and current limits

- `bev_native_cpu_parallel_v1.py`: bounded threaded validation and scoring of saved
  native readouts, including imported-byte integrity checks. It writes a separate
  output and consumes a pinned configuration. Its native-panel protocol does not
  automatically cover Track K/T reports.
- `r3_final_async_*_v1.py`: score/release/CPU-publication separation, durable launch
  uncertainty, owned failure terminals and prior-consumer fencing. A generated closure
  still requires the actual campaign, final selection, concrete execution configuration
  and independent review. Component tests do not demonstrate a deployed final run.
- `r3_monitor_registry.py` and `watchdog.py`: scripted lifecycle, progress and log
  summaries. A stage-local count is not an experiment-wide completion percentage.
- `bev_successor_prepare_queue_v3.py`: prepare-only successor controller with
  SIGUSR1 wakeup and a 600-second fallback. It verifies the predecessor's durable
  release and physical generation without waiting for CPU result acceptance.
  Post-spawn publication failures clean up owned builders; uncertain cleanup writes
  an explicit reconciliation requirement. Existing node directories are never
  automatically retried. It does not review or launch NPU experiments, and a wakeup
  receiver alone does not provide a production release-event sender. Version 1 is
  retained for contract regression tests; use version 3 for new configurations.

The successor suite is `python3 -B -m unittest
tools.test_bev_successor_prepare_queue_v1 tools.test_bev_successor_prepare_queue_v3`.
Its 45 test executions include inherited repetitions, not 45 distinct behaviors.
Lifecycle tests establish cleanup and contract behavior, not a measured utilization
improvement or acceptance of any specific experiment configuration.

Relevant regression suites are `test_bev_native_cpu_parallel_v1.py` and
`test_r3_final_async_*.py`. Current measurements and acceptance scope belong in the
[Wiki](https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions); process logs
and detailed review evidence remain local/Ceph.
