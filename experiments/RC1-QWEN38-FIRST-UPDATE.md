# RC1 Qwen3.8-27B first-update fixture

Pre-registered 2026-11-06 before NPU admission. Scope: one actual four-rank LoRA forward/backward/update/checkpoint fixture on server175. This is engineering evidence for defect12, not decision-v7 training, a DEV/TEST measurement, resume equivalence, or a new release. An exit-only or no-op pass is degenerate; actual nonzero gradients and adapter changes provide the discrimination counterpart.

## Fixed inputs and execution

- Model: `/mnt/cephfs/models/Qwen3.8-27B`, revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
- Existing image: `sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`; CANN entrypoint and mounted accepted verl/site tree.
- Data: historical 4096-row `/mnt/cephfs/xingchao/docker/verl_v030_20261029/data/sft_train.parquet`, actual `code/raw_sft_dataset.py:RawCompletionSFTDataset` under that root. No DEV/TEST access.
- Four ranks, physical chips0–3 with identity mapping; FSDP2, bf16, global batch4, microbatch1, max length256, static batching, LoRA r8/alpha16/all-linear, learning rate1e-5. Engine seed42; actual sampler seed0, epoch0.
- Scheduler horizon2, resume disabled, checkpoint after step1 and controlled stop immediately afterward. Only phase1 is authorized by this record; second batch is a saved reference, not a second update.
- First two zero-based parquet indices per rank: rank0 [2732,155], rank1 [1810,2864], rank2 [3111,2423], rank3 [2738,2918]. Actual CPU tokenizer/dataset/collator/stateful-loader reproduction passed twice. Seven of eight prompts left-truncate116–234 tokens; complete answers plus EOS survive with2–7 non-circular shifted answer targets. Preserve this behavior; it is not evidence about prompt quality.

## Bounded acceptance

Require actual27B loader/class and raw-load accounting; finite loss and participating gradients; globally nonzero finite text LoRA gradient and adapter update; optimizer bound only to LoRA; finite clipped norm and adapter values; unchanged frozen parameters across the update. Record unused vision gradients. The one-time frozen-shard CPU comparison is instrumentation for this fixture and must not become ordinary training behavior.

Require each rank's model/optimizer/extra checkpoint files, scheduler/RNG presence, actual controlled step-one stop, retained container identity and terminal exit matching the phase marker. Presence does not prove restored state or resume equivalence. Missing or contradictory evidence is failure or unknown; exit0 alone is insufficient. Report chip count, per-chip throughput and reserved memory; label throughput as instrumented because comparison overhead is included and checkpoint serialization is not part of the current batch timer. No accuracy, scientific training benefit, bf16-noise or equivalence claim follows.

## Prepared deployment and scheduling

Persistent stage: `/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/qwen38-first-update-runtime`.
Config: `config/fixture.json`; output: `runs/qwen38-first-update-20261106-1820-p2868240`; attempt: its `attempts/qwen38-first-update-20261106-1820-p2868240` child. Exact command is staged in `COMMAND-phase1.txt` and guarded Docker argv in `DOCKER-COMMAND.txt`.

Config SHA256 `b1f5ec09d233436ede103be77b223f73c5f5975635030b4c8d7aa9ba32cb2bab`; stage manifest `5940ea61786cad76ea64f58961ef72178a4cd2335fd2bb9488705dc6497a81c3`; prepared STAGED `51e1d6753b5bb25c46fabbd0086725e5836b63f290e8acb6e811f5a919f3515e`. B1 renderer correction and G1/G2 source/purpose corrections independently passed; accepted source manifest `699309929d9fc174614854a23b5f113e5af8c0754caebc0b941faf7595467df6`. Local bounded evidence is retained under `.local/releases/engineering-base-rc1/tasks/` for reproducibility; source and data receipts are reused.

Finish CPU preparation and publish this record before admission. Existing TEST work on chips0–3 has priority through all assigned successors; no reservation, drain or preemption. Wait on durable inference/release metadata with low-cost scripts, then let the accepted group controller verify current physical ownership and atomically claim all four cards. Do not run its10-second full-probe wait while known TEST work is still active. CPU scoring/analysis is not a resource prerequisite. Fresh host-memory/checkpoint-space sufficiency and exact persistent bindings must be checked before admission; CPU staging observed about2TB available RAM and714GB Ceph space, transient values rather than reservations.

Run detached with persistent launch/controller logs and exit marker, retained Docker container, per-rank progress and phase marker. Reuse the exact stored relaunch/observe records. Unknown launch or existing claim/intent must be reconciled, never blindly replayed. Release proof can fail after the ledger commit; reconcile ledger, intent and proof together. Source/configuration copies remain protected throughout execution. A failed phase preserves evidence and requires a separately identified retry; no automatic outcome-driven rerun.
