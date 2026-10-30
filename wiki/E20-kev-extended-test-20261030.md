# E20 — Kev hard-v1 and documents-v1 native reference tests

Preregistered 2026-10-30 before launch. Models: released Kev 0.8B, 4B and 9B.

## Purpose and hypothesis

Defects 12 and 16 require valid measurements and comparable reference evidence. Evaluate
the existing released checkpoints on the exact frozen official test files. Memorizing
labels is the unconstrained optimum; this evaluation does not demonstrate unseen
generalization or NGA training benefit. Constant outputs can pass structural checks;
preserve per-task metrics and independent metric recomputation. Accuracy is not consistency.

## Frozen setup

Use original Kev pointer head, release temperature, fp32 backbone, eager attention,
merged adapter, reference GDN, HF32 disabled, same pinned bases as E7/E9/E12. No test
tuning, calibration, omission or truncation. Host 175 and existing immutable image only.

| Suite | Test records/questions | Test SHA256 | Context state/branch/packed |
| --- | ---: | --- | --- |
| hard-v1 | 700/1088 | `246ee92234d33f8e3f10ac6e1542651531b128fd7cc66f3a9964589b77dfa22b` | 7552/8192/9216 |
| documents-v1 | 574/936 | `742d04a1abc2207bd3e4f24b281f483cdc69238e4da747cbbc3774e836f2e557` | 8192/8192/16384 |

Both are under the Kev source repo `evals/`; every test ID is unique. Devtools-v1 is
excluded from this run because its historical ID collisions need a separate protocol.
Headline n is 1088/936. Native question-micro accuracy, one-hot summed Brier, ECE10
and NLL are reported at saved temperature and raw T=1 separately. Additional original
diagnostics remain labeled as native outputs unless independently recomputed.

## Execution and acceptance

Each size uses a new `reference_inference/kev{08,4,9}_extended_20261030/` directory.
Before its formal inference, tokenize every official development record in both suites,
select the longest packed record per suite (first index breaks ties), and infer it twice.
Strict native encoding must succeed without truncation and produce finite normalized
probabilities; record per-chip throughput, chip count and reserved memory. OOM or any
error blocks that model's full tests. This measures a bounded resource check, not a
complete input-length safety proof or test score. The original driver also checks each
test record's strict context and fails rather than skipping an overflowing record.

Freeze model/base/tokenizer, native source, data/manifests, driver, probe, verifier,
wrapper, registration and exact launch/relaunch before launch. Retained detached fixed
containers use independently claimed free chips after allocation-lock and live-device
checks; never chips 1/2 running Open-Jev or others' chips 6/7. CephFS stores logs,
heartbeats, atomic item receipts and terminal markers. The wrapper automatically runs
full inference only after probe success, then independent verifier only after full success.
Success requires complete records/questions, independent metrics and identities, wrapper
and container exit 0. Only then release resources. Errors preserve all evidence.

Published hard_test and docs1_test comparisons use the correct release entries where
available. A missing released panel is not substituted with a different split. The
decision/transfer-specific comparison helper is not used for these suites.

## Results

2026-10-30 execution: all frozen files were rehashed on 175 before each claim/launch.
The allocation lock and live Docker maps were checked before assigning chips 0/4/5.

| Model | Chip | Frozen files | Retained container ID |
| --- | ---: | ---: | --- |
| 0.8B | 0 | 68 | `484fc43d4d7a1f0a031046b28462501153c5e8158fa6c78bad59ebe48b43ae7d` |
| 4B | 4 | 73 | `6c7cd28f088cedcba511b50e67247dc763e27264d3b0a3800540e65a32dfd699` |
| 9B | 5 | 72 | `f0e7f012c9f38515447cfc319bd5a39b53db71f686770a114322573780a17030` |

Names are `nga-reference-kev08-extended`, `nga-reference-kev4-extended`, and
`nga-reference-kev9-extended`. Each launch receipt records actual command/entrypoint,
container ID, immutable image, config and wrapper hashes. The automatic wrapper first
executes the frozen probe, then full evaluation and independent audit, stopping on failure.

At 16:06:43 UTC, 0.8B had advanced into full hard-v1 test, 19/700 records,
3.4302 questions/s/chip, one chip, reserved 6.334 GiB. Its longest-dev probe completed
both suites: 5,086 packed tokens hard / 5,164 documents, repeat throughput 1.55657 /
1.60443 questions/s/chip, reserved 7.84375 / 10.96484 GiB. Full development tokenization
covered all 700 / 568 records before selecting these inputs.

4B also completed its longest-dev probe: same longest token counts, repeat throughput
0.69582 / 0.65999 questions/s/chip, one chip, reserved 26.27148 / 32.50977 GiB. Probe
terminal and report hash were checked. 9B was still loading at 16:06:49 UTC.
No full test score or successful final audit is claimed at this point.

16:08 UTC update: 9B longest-development probe also completed, with report hash and
terminal verified. Hard/documents repeat throughput was 0.51986 / 0.49713 questions/s/chip,
one chip, reserved 40.68164 / 46.91992 GiB. It automatically entered full-evaluation model
loading at 16:08:17 UTC. The 0.8B and 4B full hard-v1 jobs had reached 104/700 and 19/700
records at 16:07:43 / 16:07:31 UTC respectively. All three retained containers were running.

The unchanged reference-driver CPU tests passed all seven cases. Probe compilation passed;
actual strict encoding and runtime execution provide its resource evidence. No training
or Astra approval is claimed.

## Verdict

Pending.

**2026-10-30 16:12 UTC review correction:** the first frozen probe stored plain per-suite
JSON and did not enforce exactly two saved passes on resume. Fresh runs did execute both
passes; the orchestrator checked both entries in each report, positive timings and terminal
report hashes for all three sizes. These observations do not validate arbitrary resumed
probe receipts. Repository code now uses a checksum envelope and checks exactly two passes,
positive finite timings and matching token counts; five valid/corrupt/empty/timing/token
tests passed. Running frozen code remains unchanged. Do not automatically restart these
three runs through the old probe reuse branch: independently review existing probe evidence
first, or register a corrected new run. No actual crash/recovery claim is made for E20.
