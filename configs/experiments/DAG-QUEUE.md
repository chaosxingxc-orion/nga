# Dependency-aware experiment queue

The owner requests multiple useful future experiments per NPU, dependencies represented as a graph, and CPU analysis asynchronous to NPU execution. `tools/experiment_dag.py` is a separate versioned planner and composition seam. It does not mutate frozen FIFO/successor services or their running experiments.

Configuration uses `nga-experiment-dag-v1`: explicit nodes, priority, CPU/NPU lane, a fixed device set, source pins, registered adapter/version, exact action/review pins, missing preparation work, and typed dependencies. The current planning target is two ready tasks plus three reserve tasks per card, configurable rather than a scientific threshold. A shared multicard task is counted in each involved device's coverage; counts are not additive unique tasks. No filler or duplicate completed experiment is useful reserve work.

## Dependency semantics

- `resource_release`: exact resource transaction establishes release; successful or failed computation may release a device.
- `artifact`: required output identity/content is available and bound; merely exiting is insufficient.
- `numerical_equivalence`: independently accepted numerical comparison, not a TEST quality score.
- `scientific_admission`: a real scientific decision under the existing preregistration; never inferred from operational success.
- `success`: a verified successful predecessor exit under its adapter contract. Running is not success.

An unrelated ready task can bypass a blocked higher-priority task. A failed node blocks its descendants, while an unreleased device continues to block other users of that device. Observed running/uncertain/failed ownership takes precedence over a contradictory free snapshot. CPU jobs have an independent configurable slot count and only their actual scientific/artifact dependencies.

## Commands and deployment boundary

`python3 -B -P tools/experiment_dag.py --config GRAPH.json --snapshot SNAPSHOT.json --out NEW-PLAN.json` validates a graph and produces a read-only proposal. It refuses to overwrite an existing output. A `digest_only` snapshot is useful for preparation/coverage; it is never launch authority. No CLI command starts a model.

The optional Python dispatch seam accepts a trusted registry injected by a reviewed composition root. Each adapter must validate its complete exact action/review/attempt/device identity, reconcile retained runtime observations, and perform live resource admission plus detached launch under the existing resource lock. No production adapter is currently supplied. A graph field saying `reviewed_dispatch` cannot substitute for the actual adapter and its genuine receipt verifier.

Dispatch writes an immutable intent before a possible remote effect, including graph and action identity. After restart, an absent or uncertain runtime remains uncertain and retains its devices; it is never automatically launched again. Observation or launch failure is isolated to the affected node/device; independent branches continue. Resource release remains an adapter-verified fact. The planner never writes scientific acceptance.

## Acceptance and remaining work

Functional tests exercise cycles, unknown/duplicate edges, strict integer types, missing/changed admission, same-card bypass, failed dependencies, external owner conflicts, multicard all-device availability, CPU/NPU independence, durable intent and restart, and independent progress after a launch exception. These use CPU fixtures and prove neither live deployment nor hardware throughput.

Before production use: bind real frozen package adapters and all executable dependencies, independently review exact graph/action semantics, confirm per-card ownership/priority under resource lock, and deploy the controller detached with durable logs/terminal/relaunch and event/approximately 600-second monitoring. Queue changes create a new graph generation and reconcile existing intents; no live graph mutation. Existing external successor ownership must remain external until a separately reviewed handover.

Model quality work remains split-correct: public fixed-base TEST baselines are separate from DEV numerical/efficiency exploration; never tune from TEST. Opportunistic multicard work requires verified idle devices and no ready queued task under its joint resource policy. Single-card LoRA remains unchanged.
