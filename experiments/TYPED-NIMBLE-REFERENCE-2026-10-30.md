# Initial Nimble on Typed Decisions: native five-field adapter

2026-10-30, before E28 execution. Defects 12/16: preserve typed input semantics and measurement provenance. Constant output or gold leakage is a degenerate optimum. Gold-only changes must leave the prompt unchanged; candidate order/content changes must change its mapping, while wrong/missing fields and unsupported widths must fail. Accuracy is not decision consistency.

Population: exact original `LocalLLaMA/typed-decisions/all/test-00000-of-00001.parquet`, SHA256 `4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`, 400 states / 2,000 questions, all five questions retained per request. Decode state/questions as the original scorer. Serialize object state as Unicode JSON using the original Nimble adapt_input convention; IDs/gold/factors never enter context or schema.

Use original adapter `594dfdcfb6f94e3d0c0db7535180d3c71689169a`, base Qwen3.5-9B Instruct `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, original v1 parallel_schema builder, T=1, max 2,048 tokens per field. Each requested field receives the full five-field schema, original question order and candidate order. Boolean choices are false/true; nominal names remain unchanged; ordinal choices use original index strings. Missing/null descriptions remain absent, empty strings remain empty; no invented text. Unsupported non-string level definitions fail rather than being silently rewritten.

First execution is CPU-only full-token preflight on 175 using the existing immutable image. Freeze base/adapter/native code/data/tool/tests/wrapper/preregistration before launch, keep a retained detached container, heartbeat, CephFS log, structured terminal, exact launch command and config/output hashes. Every field's candidate IDs, token count and prompt hash are recorded. Any overlength field blocks the whole 400-state population; no truncation or dropped rows. Synthetic five-field checks cover all types, nested Unicode state, gold invariance and candidate discrimination.

Formal NPU inference remains unlaunched and requires separately reviewed execution wiring, repeated synthetic native forwards, runtime/throughput checks, safe resource claim, item resume and a Nimble-specific independent provenance verifier. Intended forward preserves E25 BF16 safely merged backbone / FP32 candidate LM-head projection with original v1 prompts. Common metric formulas follow E26: original soft-gold arithmetic on stored native probabilities, ECE10 bins and strict validity denominators; this is not a vLLM/wire equivalence claim. E26's Kev head metadata verifier cannot be reused as Nimble provenance proof. No new training, temperature fitting or benefit claim.

## 17:18 UTC token-only result

The retained CPU execution completed all 400 states / 2,000 prompts with maximum
1,312 tokens; terminal, wrapper and Docker exit code are zero. Full input/schema
mapping and synthetic counterparts passed. The 136-file frozen dependency closure
is complete; see E28 for identities and report hash. No formal inference was
launched. Before launch, add runtime checks, synthetic repeated forwards, precise
item recovery and independent Nimble checkpoint/prompt/output acceptance; the
unlaunched helper is not sufficient evidence of readiness.

## Pre-inference execution amendment, 2026-10-30

The separate `typed_nimble_inference.py` command is prepared for synthetic `probe`
and whole-population `inference` modes. The completed token-only artifacts stay
immutable. Before either mode, freeze the exact adapter/base/native source, all
execution and verification scripts, runtime package versions, original scorer,
wrapper, relaunch command and this protocol. Both launches require an internal
implementation-review receipt bound to the new config hash; this records engineer
review and does not request new user authorization. Use only free chip 3 on 175,
under the shared allocation lock and actual live Docker device checks.

Runtime is the existing immutable image with torch 2.10.0+cpu,
torch_npu 2.10.0.post7, transformers 5.14.1 and peft 0.21.2. Preserve original
BF16 CPU safe merge, BF16 backbone, SDPA, and native FP32 candidate-token
projection. Model loading must report no missing/unexpected/mismatched/error
keys. A full five-field synthetic request must pass two forward calls, positive
finite timings and memory, valid probabilities and probability drift <= 1e-5.
Probe throughput is admission evidence only, with one chip and reserved memory.
Formal inference reruns this synthetic admission before the first test record.

Each of the 400 item receipts binds ordered question/candidate names, candidate
token IDs, prompt token hash/count, typed outputs, logits, native probabilities,
input/config identities and positive duration. Resume checks retained Docker
identity/image/command/device, frozen files and exclusive allocation, preserves
old terminal artifacts, and revalidates every reused receipt against fresh prompt
construction. Successful/live executions cannot be resumed. A launch crash before
an allocation receipt is fully established requires reconciliation; automatic
recovery of every host/Docker failure is not claimed.

The separate CPU verifier reconstructs schema independently of the driver and
re-tokenizes all five prompts per record with the pinned native v1 builder. It
checks original adapter digest/base revision, complete dependency closure, exact
400/2,000 coverage, all logits/probabilities/typed values, and independently
recomputes original soft-gold accuracy/KL/summed Brier/ECE10 and strict counts.
Only T=1 is reported: this model has no second serving-temperature panel. Original
rounded gold remains unnormalized; native probabilities are normalized by the
original arithmetic. Expected-score MAE remains deferred. This is native-readout
arithmetic, not original HTTP/vLLM equivalence. Review flags remain visible.
The CPU finisher requires the successful structured inference terminal, wrapper,
actual matching retained container exited/0 and a successful independent audit.
