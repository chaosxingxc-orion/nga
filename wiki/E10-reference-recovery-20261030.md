# E10 — Actual interruption and recovery of native reference inference

Status: preregistered before launch, 2026-10-30. Engineering development run only.

## Purpose, hypothesis and counterpart

Verify actual process interruption preserves committed inference records and resumes the
remaining work. Defect registry row 12, measurement validity. The degenerate verifier
could accept any persisted file or refuse every restart: valid resume must succeed, while
a changed probability in a copied receipt must be rejected. Prefix bytes must remain
identical after restart and the final eight-record expected set must be complete.
This does not measure model quality, calibration or cross-device equivalence.

## Frozen setup

Host 175, physical chip 3 only after allocation and live Docker mapping verification.
Use the existing immutable image from E7, native Kev-0.8B pointer head, float32, eager,
reference GDN, HF32 disabled and checkpoint serving temperature. First eight decision-v7
development records, fixed before inference; no official test is read. Freeze base,
checkpoint, tokenizer, development data, manifest, upstream source, worker, original
E7 persistence helpers and guarded resource restart code. Store code outside mirror trees.

## Procedure and acceptance

1. Detached retained container `nga-reference-recovery`, CephFS output at
   `/mnt/cephfs/xingchao/experiments/jev/reference_inference/recovery_20261030/`.
2. Persist records 0 and 1 using E7 atomic payload/hash envelopes, write INTERRUPT_READY,
   and wait at an explicit injection barrier while emitting heartbeat. The barrier tests
   recovery of committed work; it does not claim coverage of every possible kill instant.
3. Save committed file hashes, SIGKILL this container only, and verify authoritative
   exited/137 state plus absence of successful terminal. This interruption is intentional.
4. Write the continuation marker, then restart the same container using the guarded
   host helper. It checks allocation, physical device conflicts and immutable image.
5. Require worker report reused=[0,1], computed=[2,3,4,5,6,7], all eight records with
   expected input identity and valid native predictions, prefix hashes unchanged and rc 0.
6. In an isolated temporary copy, change a committed probability without updating its
   receipt hash; require the E7 read_record helper to reject it. Do not corrupt the run.

CephFS holds logs, five-second timestamp/progress heartbeats, per-chip throughput and
reserved memory, frozen launch and exact restart commands, terminal and verification
report. Release chip 3 only after final terminal and container exit are both verified.
No changes to E7/E8 or other agents' containers. No new training or candidate test reads.

## Results

**2026-10-30 execution:** container
`f5f7acac8edf2b440b8288225af251f548d52e155a1a251ee45480e8d5c05235`
was launched detached on chip 3 after allocation and Docker device checks. At the
preregistered barrier it held exactly two committed records. Their SHA256 values were
saved in `PREFIX_BEFORE_CRASH.json`. A real `docker kill --signal=KILL` terminated only
this container; `INTERRUPTION_EVIDENCE.json` records authoritative exited/137 state and
absence of successful terminal. The chip remained claimed through the interruption.

The guarded host restart helper started the same retained container. It revalidated frozen
inputs and loaded the native model, reused precisely records [0,1], computed [2,3,4,5,6,7],
and wrote rc 0 at **14:48:02 UTC**. Wrapper DONE and Docker exit also report 0. The eight
expected records, input identities and all 63 frozen file hashes were verified; both prefix
files remained byte-identical. The corruption counterpart changed a copied persisted payload
and was rejected as `Changed record payload`; the original artifact was not modified.

`RECOVERY_VERIFICATION.json` records `VERIFIED_BOUNDED_RECOVERY`. Six CPU restart-guard
tests passed, covering valid interrupted/failed restart and refusal of successful runs,
reassigned chips, live device conflicts, running handles, wrong image and wrong mapping.
Final container exit and markers were checked before chip 3 was released. No model-quality
metrics or official test results were generated.

## Verdict

The bounded real interruption and recovery succeeded. It complements synthetic corruption tests;
it does not exhaust all filesystem, concurrent-writer, power-loss or NPU failure modes.
In particular, the injected kill occurred after committed writes at an explicit barrier,
not during the atomic write itself. No broader crash-safety or Astra approval is claimed.

**Same-day review clarification:** the executed frozen run used the original E7 persistence
helpers and the first resource-guarded restart helper, before the later container-identity and
exact-device-set correction. Its evidence validates the observed prefix-preserving interruption
and recovery, not the new restart helper's end-to-end behavior. Repository worker code now joins
the heartbeat thread before final STATUS publication, and its CPU tests use the strengthened
restart interface; the frozen successful run is unchanged. The orchestrator separately rechecked
all 63 frozen file hashes and the retained container's exited/0 status.
