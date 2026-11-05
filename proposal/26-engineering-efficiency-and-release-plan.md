# Engineering efficiency audit and release plan

Status: engineering recommendations for parent review; no activation or scientific acceptance. Direct analysis in the current Sol-scoped session, without nested models. Observation collection: **2026-11-05 09:58:35.963–09:58:37.225 UTC**. The normative steering point is `.local/planning/active-continuation-20261105-v1/ENGINEERING-FIRST-STEERING.json`, **09:40:40.932260 UTC**: hold new experiment dispatch, stabilize the engineering base, preserve existing remote runs. This audit launched no experiments, queried no NPU, changed no run, stopped nothing, and made no commit or push.

The recommended engineering action order starts with complete integrated delivery and CPU handoff. The available measurements establish costs, but do not rank their avoidable contribution to total elapsed time. Repeated weight hashing and unified inference JSON serialization are concrete implementation costs, but their share of production elapsed time is not isolated. Keeping cards occupied is not the optimization objective. The objective is a correct, recoverable result delivered with less elapsed time, less repeated work and bounded resource use.

## Evidence and accounting

`tools/analyze_execution_efficiency.py` reads only the specified dispatch directory, the active planning records, eleven exact run roots and named prior reviews. It imports no repository execution module, starts no subprocess, reads no environment and hashes no model weights. Local normalized input and worker tables live under `.local/reviews/engineering-efficiency-sol-20261105-v1/`; the full local audit is `.local/reviews/engineering-efficiency-sol-20261105-v1/REPLAY.json`, with 1,394 source-presence/hash entries. The public conclusion export is `experiments/ENGINEERING-EFFICIENCY-SUMMARY.json`; it excludes per-worker/run records and source paths. Missing files and timing boundaries remain explicit nulls. Source records are individually observed, not an atomic filesystem snapshot. Independent review passed six tests, exact snapshot replay and 63 assertions over 99 structured receipts; publication wording and summary scope were corrected accordingly.

Worker accounting uses CHILD start and EXIT finish, with FINAL language as a lexical limitation flag. It does not inspect raw token events. No actual token-usage fields were supplied; **no token distribution or consumption estimate is available**. Model route names describe CHILD metadata, not identity attestations. Brief/final bytes are not tokens. The category rules are published in the script; they are operational groupings, not scientific task classifications.

The only production-log access is script extraction of JSON `startup`, `model_ready`, `complete` and `failed` records from each exact host-attempt runtime file, because those boundaries are absent from the structured reports. Other log lines never enter the analysis output. Release receipts already preserve retained container ID/start/end, so fresh Docker inspection was unnecessary. No broad Ceph traversal occurred; model files were statted only by paths already in the plans.

All elapsed figures are descriptive UTC differences unless explicitly identified as same-boot Linux process-tick differences or measured local CPU durations. The active lessons record a previously measured **about 94.5 s cross-host clock offset**. Parent intent-to-claim values may cross clocks and cannot establish authorization order. Missing synchronized forward timestamps prevent kernel-time claims.

## Direct worker delivery and critical path

The snapshot has **174 task directories, 164 CHILD starts and 161 EXIT terminals: 156 exit 0 and five nonzero**. Three started workers lack a terminal; ten directories have no CHILD. Eighty of the 156 successful subprocesses (**51.28%**) have FINAL text containing an explicit limit/incomplete/blocker term. This includes legitimate scoped successes; it is neither 80 proven failures nor an artifact acceptance rate. Eighteen directories have no FINAL. Artifact completion is not inferred from exit 0.

Completed workers span **01:47:31.788–09:55:07.162 UTC**, **29,255.37 s / 8.1265 h**. Summing worker durations gives **77,954.53 s / 21.6540 worker-hours**. The union of their intervals is **28,806.18 s / 8.0017 h**. Parallel execution therefore cannot be counted as 21.65 h of elapsed delay. Open workers are excluded from those durations. Of completed worker time, **76,604.09 s** precedes the steering point and **1,350.44 s** follows it; post-steering work is not automatically a priority violation, and this includes completions of already-running workers.

| Operational category | Directories / timed terminals | Sum of worker minutes | Median / p95 seconds |
| --- | ---: | ---: | ---: |
| Engineering base / lifecycle | 20 / 19 | 127.94 | 313.55 / 908.88 |
| Experiment preparation / integration | 63 / 61 | 360.50 | 316.72 / 687.52 |
| Orchestration / observability | 13 / 13 | 72.39 | 339.00 / 837.76 |
| Review / analysis | 78 / 68 | 738.42 | 596.46 / 1,243.12 |

There are 65 explicit dependency edges with nonnegative predecessor-terminal-to-successor-start differences: median **16.48 s**, p95 **36.46 s**, maximum **108.64 s**, summed edge waits **1,227.14 s**. The latter is work-edge delay, not global elapsed delay. Dependency detection has separate timestamps in the machine evidence. A predecessor exit is not proof its artifact is ready.

The longest reconstructed explicit dependency chain has 20 nodes, **13,236.92 s / 3.6769 h**, including **291.27 s** of inter-node waits. Its actual node list is in `worker_summary.verified_chain`. It runs from scale-length applicability through diagnosis/reconstruction, unified revisions and the fresh 4B resource review. This is a lower bound on the full critical path: omitted/manual dependencies and open tasks cannot be recovered from adjacency alone. Temporal adjacency is never turned into a dependency.

### Unified v1–v6: scoped progress, repeated partial delivery

| Revision, engineering + review workers | Combined worker seconds | Start-to-review-finish seconds | Retained capability boundary |
| --- | ---: | ---: | --- |
| v1 base | 740.55 | 762.38 | Base package; later runtime/provenance fixes still needed |
| v2 build | 1,044.41 | 1,045.94 | Build qualification; later runtime repair needed |
| v3 runtime | 1,188.57 | 1,201.60 | Runtime improvements; whole-panel score came next |
| v4 score | 1,272.25 | 1,298.90 | Accepted exact-image whole-panel CPU score |
| v5 component integration | 1,800.63 | 1,822.13 | CPU score/training wiring accepted; NPU-ready subset empty |
| v6 launch-ready | 788.92 | 800.22 | CPU inference fixtures/resources scoped pass; exact activation not ready |

These twelve workers use **6,835.32 worker-seconds** across **07:12:44.317–09:37:02.610**, **8,658.29 s / 144.30 min**. Version elapsed rows and parallel component work must not be summed into that window. Additional inference/training/repair/diagnosis workers are in the full worker table, not these twelve. Passing component reviews are retained milestones; a new version name does not establish integrated release readiness. Examples of the exit/delivery distinction include `terra-final-release-v2` (908.88 s, exit 0, explicitly incomplete) and `terra-kev-cpu-bootstrap` (205.90 s, exit 0, critical path unfinished).

Repeated source closure copies are also measurable: across eleven run `code/` directories, **133 Python files, 20 unique byte identities, 1,563,013 bytes total**. There are **113 duplicate instances / 1,351,961 duplicate bytes**. Eight copies of the same 29,292-byte dataset runtime, eleven copies each of native runtime/dev loader/resource adapter, and repeated host/consumer/watcher closures increase the surface for rebinding and review. Their byte volume is small; no timed copying or review-saving amount is claimed. Frozen copies preserve provenance. Future image-owned shared components should reduce fresh scope review while preserving old closures.

## Actual run timing

Exact roots are under `/mnt/cephfs/xingchao/experiments/jev/r3_runs/`:

- `kev_documents-v1_08b_20261105_v7_configured`;
- `kev_documents-v1_{2b,4b,9b}_20261105_v11_ready`;
- `kev_devtools-v1_{08b,2b,4b,9b}_20261105_v9_ready`;
- `instruct_numeric_{08b,2b,9b}_20261105_v1`.

All eleven have matching successful runtime/host terminals, report population counts, successful release and release-to-claim hash bindings in this audit. This is a limited completion check, not a new numerical/scientific validation or complete launch-closure review. Kev CPU terminals are also successful. Numeric evidence is reused from the just-finished independent analysis; it was not reconstructed again.

Every cell below uses **one chip**. Container q/s is computed/physical-container-seconds/chip; execute-loop q/s comes from heartbeat and includes CPU validation, persistence and scheduling. It is not pure forward throughput. Memory is the report's reserved GiB, also equal to its reported peak in these cells.

| Kev task / model | Items | Container s | Startup→model-ready s | Model-ready→complete s | Container q/s/chip | Reserved GiB | Release→generic / Kev terminal s | CPU service start gap s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| documents 0.8B | 936 | 346.73 | 17.92 | 324.21 | 2.699 | 4.420 | 5.04 / 272.74 | 242.69 |
| documents 2B | 936 | 341.47 | 20.43 | 316.19 | 2.741 | 8.682 | 6.94 / 273.71 | 243.65 |
| documents 4B | 936 | 484.79 | 32.16 | 447.67 | 1.931 | 19.330 | 16.72 / 130.24 | 100.13 |
| documents 9B | 936 | 595.33 | 50.11 | 538.51 | 1.572 | 37.160 | 39.78 / 646.81 | 586.70 |
| devtools 0.8B | 1,073 | 337.91 | 17.00 | 315.94 | 3.175 | 3.717 | 4.79 / 280.66 | 250.61 |
| devtools 2B | 1,073 | 328.38 | 21.61 | 301.70 | 3.268 | 7.980 | 7.33 / 287.42 | 257.36 |
| devtools 4B | 1,073 | 431.93 | 29.28 | 398.17 | 2.484 | 17.727 | 11.83 / 179.82 | 149.76 |
| devtools 9B | 1,073 | 489.06 | 56.16 | 426.29 | 2.194 | 35.582 | 21.03 / 112.08 | 82.02 |

The CPU start gap is `(Kev SERVICE.start_ticks − generic SERVICE.start_ticks)/100`, only when boot IDs match. CLK_TCK=100 is inherited from the prior verified host observation. This is a service-to-service gap, not exact release-to-start or pure watcher sleep. Eight gaps total **1,912.92 s**, median **243.17 s**, range **82.02–586.70 s**. A fixed 600 s polling interval has a scheduling-only range of approximately 0–600 s, with 300 s mean only under an unverified uniform arrival assumption. documents 9B exceeds 600 s release-to-terminal because scoring and other work are included. Summing eight gaps does not mean the campaign could finish 1,912.92 s earlier.

The generic CPU path is started on release; the separate Kev watcher adds polling delay. CPU scoring time itself is not isolated: service records have process start ticks but no UTC/monotonic anchor, and heartbeat files overwrite earlier values. Last-heartbeat-to-terminal is only a lower bound (generic 4.65–20.88 s in these cells, except documents 9B 9.21 s after its last heartbeat); the final Kev heartbeat can be milliseconds before terminal. Neither is a complete CPU duration.

Correction to earlier planning shorthand: `KEV-FIRST-HANDOFF-LATENCY.json` reports documents 0.8B release-to-generic/Kev 6.48/274.19 s, using the allocation transition as its start. Recomputing from the release receipt gives **5.04/272.74 s**. The **1.442 s** difference is retained, not silently mixed with the receipt boundary. devtools 0.8B already uses receipt time: 4.79/280.66 s. Allocation transition and release receipt are different events.

### Instruct numeric DEV and analysis latency

| Model, one chip | Container s | Execute loop from inverse heartbeat q/s, s | Reserved GiB | Host intent→claim s | Reused numeric reconstruction s |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.8B | 30.86 | 9.54 | 4.725 | 16.60 | 1.264 |
| 2B | 41.52 | 10.42 | 9.162 | 31.85 | 1.249 |
| 9B | 91.80 | 22.52 | 38.607 | 127.29 | 1.232 |

Each run completes three inputs and **nine forwards/operands**, not three forwards. The loop includes exact comparisons, NPZ persistence and compact records. Container-minus-loop is 21.31/31.10/69.28 s; no evidence separates imports, hashing and model loading within it. Claim-to-container is 1.81–1.83 s, exit-to-release 5.52–5.66 s. Host intent-to-claim also includes admission/approval/preflight; it is not measured weight-hash time.

The independent numeric worker occupies **681.81 s / 11.36 min**. Its three reconstruction cores total **3.744 s**; that is about **182×** worker/core duration, not 678 s of proven waste. It also waited for terminals, checked lifecycle/model metadata, constructed pinned downstream candidates, tested faults and assembled delivery. The prior devtools audit core took **6.032 s**, with successful supplement **1.88 s**. These comparisons establish that preparation/publication latency can dominate seconds of arithmetic. They do not price model tokens or justify dropping validation. 4B remains WAIT_TERMINAL in the reused numeric review; no fresh 4B analysis was performed here.

## Reservations, container occupancy and utilization

The selected lease window is **06:30:31.038–09:35:36.755 UTC**, **11,105.72 s**. Eight-chip capacity is **88,845.74 chip-seconds**. Per-chip interval unions, deduplicated within each physical chip:

| Physical chip | Selected lease seconds | Selected container seconds |
| --- | ---: | ---: |
| 0 | 1,600.20 | 1,564.44 |
| 1 | 692.96 | 679.37 |
| 2 | 335.20 | 328.38 |
| 3 | 968.84 | 947.58 |
| 4–7 | No selected interval | No selected interval |
| Total | **3,597.21** | **3,519.77** |

Selected leases cover **4.0488%** of that window's capacity; actual selected container lifetimes cover **3.9617%**. The difference is **77.44 chip-seconds**, including prelaunch and release work. All eleven selected leases close; no open selected claim is extrapolated. Full claim/release and container intervals are in the JSON. Release snapshots show eight ledger entries free at documents 0.8B and documents 2B release; these are point observations, not evidence that all eight cards were idle between them.

Other historical/current jobs are outside these exact roots. Thus whole-host physical-container occupancy is bounded only by **3.9617%–100%**, and uncovered time is **unknown**, not idle. AI Core utilization is entirely unmeasured. A reserved chip can be loading, hashing, synchronizing or writing; even a running container cannot establish useful NPU computation. Conversely, a past all-free ledger snapshot cannot establish the entire window's resource availability. No utilization-maximizing launch policy follows from this evidence.

## Weight hashes and storage costs

Model weight sizes are obtained by stat from exact manifest members, without reading weight bytes:

| Model | Weight bytes per checkpoint |
| --- | ---: |
| Base / Instruct 0.8B | 1,746,942,600 |
| Base / Instruct 2B | 4,548,221,488 |
| Base 4B | 9,319,828,056 |
| Base 9B | 19,306,310,872 |
| Instruct 9B | 19,306,310,880 |

One inventory pass across eight Kev cells represents **69,842,606,032 bytes**; one across the three numeric cells represents **25,601,474,968 bytes**. In frozen Kev runtime `verify(..., model_files=True, cpu=False)`, `cpu=True` changes source inclusion but leaves full model hashing enabled. Both generic and Kev CPU consumers call that verifier. Successful runtime plus those two completed consumers imply **three weight passes per Kev cell**. Numeric `verify` hashes model members once through `d.files` and again through model inventory: **two passes per invocation**. These required completed paths imply at least **260,730,768,032 logical weight-hash bytes**.

Source composition additionally shows host main/start verification, host main/supervise verification, explicit supervise verification and runtime verification. With the two CPU paths, the normal Kev start path has six full inventory passes. Numeric main/start + main/supervise + explicit supervise + runtime verification each perform two, and three host approval calls rehash `d.files`: nominal **eleven weight passes**. Across these selected roots the corresponding nominal hash input is **700,671,860,840 bytes / 700.67 GB**. Additional independent reviews/preflights may add passes; no invocation trace counts them all. This is source-derived logical byte accounting, not measured physical Ceph traffic: page cache can serve reads, and hash time has no begin/end instrumentation. Neither a bandwidth assumption nor the largest intent-to-claim difference is used to manufacture hash seconds.

The prior Instruct reconstruction deliberately inherited accepted byte identity plus manifest, filesystem metadata continuity and read-only mount evidence; it rehashed small metadata and **did not hash weights again**. Reuse should preserve that disclosed assurance level. A future hash cache needs a trusted immutable content generation, inventory identity and mutation invalidation; an mtime-only cache does not replace byte authentication.

### Full vocabulary JSON: distinguish unified component from existing Kev runs

One 248,320-value float32 vector has **993,280 payload bytes**. Retained unified v5 CPU inference records contain 248,320 logits each and measure **4,843,560 / 4,843,673 / 4,843,850 bytes**, **4.8763–4.8766×** the vector payload. A one-pass stdlib CPU measurement on those local retained fixtures gives **0.1066–0.1104 s decoding** and **0.2107–0.2132 s encoding** per record. This measures warm local CPU serialization with no torch/model/NPU execution, not Ceph bandwidth or binary speedup.

Applying that fixture's mean bytes to 46,320 records projects **224.36 GB JSON**, versus **46.01 GB float32 payload**; a write/read pair projects 448.72 GB versus 92.02 GB. Applying the measured encode/decode mean serially projects **14,843.86 s / 4.12 h CPU work**. These are extrapolations, not observed production traffic or elapsed times. Real values, parallelism, fsync and caches may change them. Another worker owns the live binary-persistence repair; this report uses retained v5 records and a retained source overlay, not that changing working copy.

In contrast, the eight audited Kev roots already save **8,860,810 bytes across 8,036 compact records**, without full vectors. The three numeric roots save **27 NPZ operands / 29,371,752 bytes** and 8,439 bytes of compact records. Do not attribute full-vector JSON expense to those completed Kev runs. A binary migration must preserve the numeric DEV full operands and bit-exact candidate arithmetic; it must not silently expand or reduce the scientific evidence contract.

## Existing engine acceptance and remaining release work

The native DAG review (`.local/reviews/dag-native-independent-20261103-v1/ACCEPTANCE.json`) accepts **27 native + 19 planner = 46 tests** and five independent CPU probe groups. Its exact supplied graph has two `external_frozen` nodes, **zero managed executable actions**, plan-only mode, activation false, and production dispatch **NOT_REVIEWED**. The adapter recognizes legacy native-long and panel kinds, not an automatically qualified unified release. Existing CPU handoffs remain within frozen native hosts. This is why a tested engine has not replaced production orchestration: accepted component capability was never a reviewed executable backlog. Reuse planner/lease/reconciliation behavior, then qualify exact action adapters and one end-to-end managed node. Do not fork another scheduler merely to obtain a green component test count.

Unified v4 independently scores **46,320 saved records**, with zero arithmetic differences and summary SHA-256 `5809e7cded0944611d701e850639b1c9030d3e5693966a427f2af8c10c677368`. Submitted, independent, recovered and v5 reports respectively record **233.15, 125.47, 88.46 and 307.86 s** (198.67, 369.19, 523.64 and 150.46 records/s). All are CPU wall times, with no chip throughput interpretation. The **3.48×** max/min spread is not a controlled speed comparison. SIGKILL after 7,200 records recovered by full replay; **item/chunk resume was not demonstrated**.

The v5 review preserves that score acceptance and five training checkpoint fixtures, but its NPU-ready subset is empty. Missing pieces include atomic launcher/leases, durable early-failure ownership/terminals, torn-record recovery, strict boolean/index handling, actual model/driver/API qualification, LoRA and NPU resume evidence, trained-adapter inference and an inference-to-score bridge. Training 2B/4B/9B is outside v5's supported schema. v6's retained CPU review passes six tokenized requests with deterministic model substitution plus resource tests, but lacks an accepted new fixed image/launcher/whole-launch fault suite. These findings are historical baselines, not a rejection of unreviewed concurrent fixes.

## Engineering action priorities (not measured dominance)

| Rank | Bottleneck | Demonstrated impact | Confidence and next discriminating evidence |
| --- | --- | --- | --- |
| 1 | Fragmented delivery and serial review/rebinding | Unified v1–v6 144.30 min elapsed, 113.92 worker-minutes for twelve main workers; still no integrated NPU release | High for scope/durations; avoidable share unknown. Require one complete vertical transaction before scaling configurations |
| 2 | Kev watcher polling after release | CPU start gaps 82.02–586.70 s; 1,912.92 summed service-gap seconds | High for gaps; exact sleep/score split missing. Add release-triggered durable dispatch and measure actual start |
| 3 | Repeated full weight hashes | ≥260.73 GB required logical hashing; nominal full paths 700.67 GB | High for code paths/bytes; elapsed and physical I/O unknown. Instrument before making a time-saving claim |
| 4 | Full-vector JSON in unified inference | 4.84 MB vs 0.993 MB payload; about 0.32 CPU s encode+decode per fixture | High for retained fixture; production impact extrapolated. Paired binary benchmark on local and Ceph storage |
| 5 | Score replay variability / recomputation | 88.46–307.86 s per 46,320 records; restart rereads whole panel | High for reports, low for cause. Measure phases/cache/CPU bounds; authenticated chunk resume |
| 6 | Dependency polling | p95 36.46 s, max 108.64 s; 291.27 s waits on reconstructed chain | High for explicit edges, readiness unknown. Event-driven terminal notification and artifact-ready checks |

No rank is assigned to NPU kernels, batching or datatype changes: synchronized forward timing and an invariant numerical comparison are missing. Startup→model-ready spans 17.00–56.16 s for Kev and combines validation, hashing, imports and load. Model-ready→complete combines computation and persistence. Optimizing whichever phase is measured to dominate should precede proposals to change execution semantics.

## Functional and nonfunctional release baseline

Functional invariants retain fixed batch 1, float32, HF32 off, registered input order/lengths, exact tokenizer/render/readout, full-vocabulary checks where required, exact saved-population summaries and paired protocols. Trusted code must execute captured authenticated bytes; types must reject boolean-as-index, and an input/owner failure cannot create an unrelated output. Source plan/manifest/claim/release and physical container identity remain distinct authorities. Scores do not authenticate training or create TEST-selection authority.

Nonfunctional requirements cover latency, resource accounting, durable early/late failures, duplicate exclusion, process generation, bounded CPU/memory/in-flight work, per-item recovery and reproducible image-owned code. A successful subprocess is only one state. Use `component_verified → integrated_cpu_verified → qualified_runtime → exact_release_ready → accepted_delivery`, with incomplete work explicitly retained at its actual stage. The worker completion receipt should bind executable command, config/image/source identities, result population and test evidence before it unlocks a dependent task.

The audit proposes no scientific metric or model improvement. Registry linkage is to protecting **defect 12** measurement validity, **defect 16** candidate arithmetic/comparability and **defect 17** exact level rendering/type identity; elapsed time alone does not repair those defects. The unconstrained latency optimum is to skip work or reuse a constant/foreign/stale result. Therefore every speed gate is paired with positive exact-result checks and discrimination controls: changed input/definitions/order must either recompute or reject stale lineage; corrupted operands, foreign model, changed claim/image and duplicate generations must fail. This engineering counterpart does not introduce or amend a scientific invariance threshold, split or model-selection rule.

## Prospective engineering acceptance gates

These are **recommended future engineering targets**, not pre-registered scientific metrics, current passes or authorization for this audit to launch work. The parent should freeze target workloads/hosts/cache conditions before the release comparison. Avoid optimizing p95 against changed population, fewer validations or widened tolerances.

| Gate | Recommended quantitative acceptance | Rollback / failure behavior |
| --- | --- | --- |
| E0 complete CPU transaction | Exact image/config; ≥20 fault/recovery cycles covering claim→launch receipt→item commit→terminal→release→CPU→score; zero duplicate launch/consumer publications, lost claims or captured-code bypasses | Hold release on any invariant failure; retain failed attempt and original lease until reconciled |
| E1 timing visibility | ≥99% phase coverage on fixed replay; every attempt gets UTC + host/boot/monotonic anchors; separately time queue/admission/hash/load/forward/persist/CPU/report; missing phases explicit | Missing or inconsistent clock/phase identity prevents a throughput claim |
| E2 handoff / dispatch | On ≥20 same-host CPU cycles, release→CPU-start p95 ≤5 s, max ≤15 s; artifact-ready→dispatch p95 ≤10 s; exited-container→release p95 ≤10 s | Retry event delivery idempotently; retain 600 s fallback for lost wakeups. Never claim NPU while waiting for CPU publication |
| E3 immutable admission | At most one full weight hash per trusted immutable generation; later admission p95 ≤5 s under frozen warm conditions; zero stale acceptances after any inventory/generation mutation | Rehash on mutation/uncertainty; no mtime-only acceptance or removal of provenance checks |
| E4 binary persistence | Exact float32 byte round trip including signed zero; finite-value rules unchanged; full-vector file ≤1,013,280 bytes; ≥75% reduction in bytes and encode/decode CPU time against paired JSON fixtures | Keep explicit read-only v1 compatibility; new-version outputs and receipts; never rewrite historical/running records |
| E5 CPU score/recovery | Same 46,320 summary hash; matched warm target ≤150 s and no >10% regression against concurrent matched baseline; resume recomputes ≤100 already-committed items; bounded workers/in-flight chunks | Reject corrupt/foreign chunks; preserve old exact scorer and full-replay recovery. Do not treat uncontrolled 88/125/308 s runs as a benchmark win |
| E6 actual runtime, later | Only after E0–E5 and parent readiness review, qualify one registered model/runtime route, its physical/logical device mapping and checkpoint resume with unchanged registered tolerances; report one-chip throughput and reserved memory | Qualification failure holds migration; no extrapolation to unsupported scales or training modes |

No universal occupancy or AI Core utilization target is proposed. Require useful work/sec/chip and time-to-validated-result, plus memory and failure recovery. A queue depth counts only reviewed executable nodes with complete dependencies/resource bindings; inventory/planning nodes do not count. First release should activate exactly one managed action adapter; broader matrix support is a subsequent explicit capability.

## Migration and rollback sequence

1. Keep new experiment dispatch held. Leave existing remote runs and their frozen closures untouched. Finish the inference persistence/ownership path and host DAG/lifecycle work in their assigned files; use retained score and numeric reviews as dependencies rather than repeating their science.
2. Assemble one immutable image with an exact launcher, config, lease adapter, CPU event handoff, binary result/score bridge, failure terminals, checkpoints and precise relaunch command. Run the complete bounded CPU transaction and failure matrix before sending a release for parent review. Preserve scoped milestones; review actual deltas and their integration boundaries.
3. After the base is ready and parent review accepts the exact release, inspect the then-current old runs. If an old run has finished, consume its terminal and release without stopping it. If it is still running, request/persist an item/checkpoint boundary through its supported controller, authenticate checkpoint, optimizer/RNG/data cursor and already-committed item receipts, then stop only that exact generation through its owner. Preserve logs/failed/partial evidence and reconcile the actual container plus lease before replacement admission.
4. Resume from authenticated checkpoints/items in a new output/attempt generation and namespace. Compare exact readouts or existing measured training noise tolerances; a speedup may not silently alter loss/gradients, input order, population or metric thresholds. No mutable edit to an old active package. No fresh TEST selection from saved outcomes.
5. Roll back by disabling only the new dispatcher generation, preserving its uncertain launch/lease journal and reconciling live containers. Restore the previous accepted image/config/controller and resume the last verified checkpoint in a new attempt. Never delete a lease because a watchdog is stale, run two owners, silently reuse a partial item or overwrite a terminal. Keep predecessor releases and old artifacts readable for CPU reconstruction even after successor cards become busy.

This sequence is a future plan. **No old run is stopped now.** Any real runtime qualification, stop or resume remains outside this read-only audit. The user priority permits engineering preparation now and migration after the replacement is ready; it does not make unreviewed component fixes a release.

## Completed and unfinished

Completed here: reproducible collector/replay, numerical worker/dependency/parallel accounting, eleven-root terminal/lease/container audit, repeated hash/source-copy accounting, retained full-vector JSON CPU measurement, reuse of Instruct/score/DAG reviews, explicit missing boundaries, engineering action priorities, proposed release gates and migration/rollback plan. Six focused accounting tests verify interval union, dependency-chain waits, missing timestamps, exit/delivery separation and occupancy bounds; snapshot replay is checked byte-for-byte.

Unfinished by design: production instrumentation/fixes owned by other workers, real hash/load/kernel phase measurements, Ceph physical I/O timing, whole-host occupancy history, actual token usage, inference-to-score integrated runtime qualification, item-granular unified score resume, supported larger-scale training and exact release acceptance. Existing experiments remain untouched. Parent handoff: `.local/reviews/engineering-efficiency-sol-20261105-v1/HANDOFF.md`; no commit or push was made.

Reproduce current observations with `python3 -I tools/analyze_execution_efficiency.py --output .local/reviews/engineering-efficiency-sol-20261105-v1/new-audit.json --process-dir .local/reviews/engineering-efficiency-sol-20261105-v1/new-observation`. Live state may have advanced. Reproduce this exact snapshot with `--replay .local/reviews/engineering-efficiency-sol-20261105-v1/INPUTS.json`, selecting a fresh local output/process directory. Process snapshots and per-worker tables stay local; only conclusion artifacts should be considered for later parent-controlled commit.

Public summary export (the full output remains local):

```sh
python3 -I tools/analyze_execution_efficiency.py --replay .local/reviews/engineering-efficiency-sol-20261105-v1/INPUTS.json --output .local/reviews/engineering-efficiency-sol-20261105-v1/publication-audit.json --process-dir .local/reviews/engineering-efficiency-sol-20261105-v1/publication --public-summary experiments/ENGINEERING-EFFICIENCY-SUMMARY.json
```
