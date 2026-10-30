# E29 — Open-Jev on the exact Typed Decisions test

Pre-registered before E29 execution, 2026-10-30. Defects 12/16: intact typed input semantics and traceable measurement. A constant predictor or gold-leaking adapter is a degenerate optimum. Gold/metadata invariance has candidate-content and candidate-order discrimination counterparts; missing fields, wrong order and overlength requests fail.

Exact parquet SHA256 `4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`, 400 states / 2,000 questions. The native Open-Jev `compile_request` receives the unchanged decoded state and all five questions. Its released implementation deliberately emits independent question records and independent candidate prompts, except one yes/no prompt for noul. Preserve this native behavior; do not invent a shared five-field prompt or claim joint-schema equivalence with Kev/Nimble. Preserve all question IDs/order, choice names and definitions, false/true order, ordinal index mapping, original state JSON rendering and chat template. No gold, factors or dataset ID enter the prompts. Empty versus missing descriptions follow native compiler rules.

Checkpoints and bases are exactly those of E14/E18: Open-Jev 2B / Qwen3.5-2B revision `15852e8c16360a2fea060d615a32b45270f8a8fc`, temperature 1.518796342858676; Open-Jev 9B / Qwen3.5-9B revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, temperature 1.8969118766347646. Native BF16 backbone / FP32 decision head, unmerged adapter, SDPA, maximum 4,096 tokens per candidate, no clipping or truncation. First execution is CPU-only native compilation and token preflight of the whole population for both tokenizers. A single overlength candidate blocks that model's full population. No inference is authorized by a successful token-only preflight alone.

Metric intent follows E26's frozen original accuracy / KL / soft Brier / ECE10 arithmetic on native probabilities, separately serving temperature and raw T=1. Rounded gold stays unnormalized; prediction normalization, first argmax, KL floor and ECE bins follow the original pinned scorer. Strict validity counts retain all 2,000 questions; invalid native probabilities fail rather than silently dropping rows. Open-Jev noul wire has no probabilities field; raw-readout scoring is explicitly not original HTTP/wire reproduction. Expected-score MAE remains deferred as in E26. No calibration, prompt selection, new training or benefit claim.

CPU runs use 175 only and the existing immutable image, retained detached fixed-name containers without NPU devices. Freeze exact base/checkpoint/native code/data/scorer/tool/tests/wrapper/protocol/launch/resume files. Persist per-state input/request/native-record/prompt/token identities and candidate lengths, validate receipts upon resume, preserve failed terminal history, refuse to overwrite successful terminal. CephFS log, timestamped heartbeat, structured terminal, wrapper exit and exact relaunch command remain inspectable. A later formal inference implementation must add two synthetic native forward passes, frozen runtime, actual token binding, item-level prediction recovery, locked chip allocation, independent scoring/provenance and retained Docker exit checks before launch. Existing public test and E24 chip ownership are unaffected.

## 17:44 UTC CPU admission result

Both models completed all 400 states / 2,000 questions / 6,500 independent native
candidate prompts with maximum 586 tokens, below 4,096. Zero overlength; terminal,
wrapper and retained Docker exit 0. 88/91 frozen files cover all 87/90 required
paths for 2B/9B. Identity/coverage/length summaries have separate artifact checks;
no independent re-tokenization or model inference is claimed. E29 formal execution
still needs actual runtime admission, native readout item receipts, safe allocation
and its own independent metric/provenance verifier.

## Native execution implementation, before NPU launch

Each state is compiled by the pinned native `compile_request`; each of its five
native question records is passed separately to the unmodified DecisionModel
forward. Candidate batching inside that question, right padding, SDPA, BF16
unmerged backbone and FP32 scalar head match the original public-test path.
No cross-question batching or prefix cache is introduced. A tokenizer observer
captures the actual padded tensor input, removes right-padding using its mask,
and checks every candidate token sequence against the full-population preflight.
The observer returns the original tokenizer object output unchanged.

Freeze torch 2.10.0+cpu, torch_npu 2.10.0.post7, transformers 5.14.1 and peft
0.21.2. Each model must pass two full five-question synthetic native calls,
finite positive timing/memory, valid complete distributions and repeat probability
delta <=1e-5. Formal inference repeats that admission. Original wire responses are
saved and independently reconstructed, but raw probability scoring remains distinct
from the original wire scorer. Native logits are saved before temperature division;
serving and raw T1 share those exact logits. Expected-score MAE remains deferred.

Independent CPU acceptance reconstructs native prompts and re-tokenizes all 6,500
candidate prompts, checks question/candidate identities, wire mappings, model/base/
temperature metadata, complete dependencies, every item receipt, full 400/2,000
coverage, and original arithmetic with a separate implementation. Suspicious
extremes, identical cells and small groups retain review flags. The finisher checks
retained actual container identity/image/command/device and exited/0 in addition
to successful structured terminal and wrapper. Parent review binds each launch
configuration. New probes may use reviewed completed E26 resources on chips 0/4/5;
E14/E18/E24 chip 1/2 ownership is never implicitly transferred. Failed prediction
runs can resume only with matching identity/allocation and preserved historical
terminals. Host interruption between create/receipt/allocation/start still requires
reviewed reconciliation; full autonomous host-failure recovery is not claimed.
