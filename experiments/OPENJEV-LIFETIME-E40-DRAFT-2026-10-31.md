# E40 draft: full-shape Open-Jev GDN lifetime experiment

Status: candidate implementation and pre-registration draft; **not frozen, no NPU launch authorization**. This does not amend E36/E37/E38 and does not grant JEVal numerical admission.

## Purpose and hypotheses

This engineering experiment serves defect 12/16 by preserving full candidate identity and making the native comparison executable. Hypothesis: releasing dead Python references can reduce allocated peak without changing arithmetic, shapes or complete outputs. The unconstrained minimum-memory solution skips candidates or computation; the discrimination counterpart requires all original candidates, token/mask identities, every returned logit/probability/wire value and exact repeated output agreement. A smaller memory number with missing computation is failure.

L1 and L2 are tested separately and together. No expression, operation order, dtype boundary, candidate batch, padding, matmul decomposition, backend or offload change belongs to these candidates. A mismatch rejects that candidate under the exact protocol; a memory non-improvement is retained as a negative result. Neither event changes prior tolerances.

## Candidate implementation

`tools/openjev_lifetime_candidate.py` accepts only native source SHA256 `0e2cd8dc50885b2701d26b116c585eedcdc62a24080ec34345af55b963126ded` and extracts only `torch_chunk_gated_delta_rule`. It inserts top-level AST `Delete` statements. Removing those statements must recover the original function AST exactly. It compiles only that function with the verified loaded native function's globals; it does not execute the rest of the input source module.

- L1: after reshape delete old `value` and `beta`; after triangular loop delete `row/sub`; after new value calculation delete `v_beta`; after `k_cumdecay` delete `k_beta/attn`.
- L2: after the recurrent loop delete full tensor references and loop views (`q_i/k_i/v_i`, etc.), plus L1's still-held intermediates when L2 runs alone.
- L1L2: both groups without double deletion of L1 names.

An external wrapper rejects training/gradient mode, cache/initial state, final-state output, extra kwargs, non-64 chunks, empty or incompatible shapes and gradient-bearing tensors. Scope is the native 2B/9B Q/K/V shape with head dimension 128 and 16/32 value heads. The launcher must additionally freeze/verify framework, dtype, backend, model and hook setup; the wrapper alone does not authenticate those dependencies. AST identity establishes expression preservation only, not numerical equivalence or actual storage lifetime.

## Proposed setup to freeze before execution

Host `npu` / `k8s-node1`, fixed existing image `sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`. Model identities and native temperature come from each size's E38 frozen plan. Use metadata-selected inputs 4200, 9027 and 8409, with original full candidate sets and original global padding. No gold-based selection. No maximum-255-candidate experiment in this first stage.

Per size/input: original, L1, L2 and L1L2 each have two uninstrumented repetitions. Instrumented measurements are separate and must have matching uninstrumented controls. Before startup, the exact plan must enumerate all forwards, input/token/mask hashes, model/config/source hashes, path order, seeds if any stochastic operation exists, chip ownership, memory headroom, failure conditions and retained outputs. Baseline observations do not replace the fresh paired baseline. No operation is allowed outside `inference_mode`.

## Measurements and gates

- Verify every candidate, original input/token/mask hash, full logits, temperature, probabilities, wire, tie behavior and serialized output against the original path. Exact comparisons must preserve signed-zero/serialization rules as in E38; checking final decisions alone is insufficient.
- Both repeats within each path must be exact; each candidate must match original. Instrumented/uninstrumented outputs must agree. Every mismatch remains in report with identity and first observed difference, not an invented causal attribution.
- Collect time per full forward, questions/s/chip and tokens/s/chip, chip count, peak allocated/reserved memory, baseline memory and stage-specific allocated memory. Compare uninstrumented throughput only with like instrumentation and input shape. No averaging away an OOM or failed cell.
- Storage alias/liveness observations must verify view-retained tensors and actual release behavior. Lower allocated does not imply lower reserved. No throughput benefit can be claimed from AST checks.
- The exact safety envelope/headroom and stop rule must be frozen after engineering preflight and before this NPU experiment. Success on three safe shapes cannot establish safety on all 3,675 eligible shapes, full attention or MLP workspace, or the 255×2156 maximum input.

## Execution and acceptance requirements

Fixed-name detached retained Docker, CephFS logs, heartbeat, per-item identity-bound receipt and resumable completed-item handling, exact relaunch command, wrapper EXIT, terminal marker and real Docker exit are required. Uncertain forwards, failed publication or mismatched identity must fail closed rather than silently rerun. Independent verifier reconstructs all comparisons and retains suspicious successes, counts and flags. Wiki setup is written before execution and results afterward. Actual Astra must review the frozen code/plan and later the bounded results. Resources are released only with the applicable independently reviewed transaction.

The candidate requires fixed-image tensor tests and integration with the experiment driver before any NPU launch. Current CPU tests prove structural generation/guard behavior only. This draft is not the runner, a frozen metric registration, a release approval, an efficiency result or a JEVal test score. If L1/L2 cannot establish a safe full workload, tensor/parameter byte offload is a separate future experiment.
