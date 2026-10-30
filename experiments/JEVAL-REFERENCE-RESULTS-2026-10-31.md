# E33 — completed JEVal native reference results, 2026-10-31

Kev-0.8B and initial Nimble v1 have completed actual inference on the original 11,257 JEVal rows. Each run has 11,257 identity-bound receipts, successful inference/finisher/hardened terminal markers, and retained Docker exit 0. The independent audits retain **6 Kev flags and 30 Nimble flags**; their status remains `VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED`. This document records bounded diagnoses and measured results for parent review; it does not erase flags or grant training admission.

The [frozen E33 protocol](JEVAL-REFERENCE-INFERENCE-2026-10-30.md) governs these numbers. Defects 12/16 concern task identity, measurement and external generalization. Keeping all unsupported/overlength rows in the denominator rejects the degenerate optimum of dropping hard inputs. The original scorer is unavailable: these are local native-response paper-formula measurements, not reproduced paper scores, source-macro averages, or a paired consistency metric.

## Registered native metrics

| Model | Native temperature | Classification correct / 10,938 | Accuracy | Valid classification | Raw summed Brier | ECE10 | Score MAE | Valid score / 319 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kev-0.8B | 2.35109581257 | 5089/10,938 | 46.525873% | 9,911 | 0.598302104 | 0.163216356 | 1.121768025 | 319/319 |
| Nimble v1 | 1 | 5394/10,938 | 49.314317% | 7,694 | 0.433576240 | 0.135360806 | 0.842948718 | 312/319 |

Classification accuracy divides by all 10,938 original choice/noul rows, including ineligible rows as wrong. Brier and ECE divide only by valid classification counts (9,911 Kev; 7,694 Nimble). Brier uses raw wire probabilities without renormalization; noul reconstructs `[1−p,p]`. ECE10 uses native returned choice confidence (Kev chance-adjusted, Nimble selected probability), selected binary probability for noul, and upper bins at exact boundaries except 1.0. These are disclosed local conventions.

Score MAE is in original level units over valid scores, with no K−1 normalization: Kev returns the four-decimal expected level; Nimble returns the selected integer level. The excluded 7 Nimble score rows remain visible against the complete 319-row population. Different valid populations prevent treating valid-only calibration or MAE differences as a controlled same-row comparison.

## Coverage and type denominators

| Model | Type | Original rows | Valid | Ineligible | Correct | Full-denominator accuracy / valid-score MAE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Kev-0.8B | choice | 9,582 | 8,625 | 957 | 4070 | 42.475475% |
| Kev-0.8B | noul | 1,356 | 1,286 | 70 | 1019 | 75.147493% |
| Kev-0.8B | score | 319 | 319 | 0 | — | MAE 1.121768025 |
| Nimble v1 | choice | 9,582 | 6,512 | 3,070 | 4381 | 45.721144% |
| Nimble v1 | noul | 1,356 | 1,182 | 174 | 1013 | 74.705015% |
| Nimble v1 | score | 319 | 312 | 7 | — | MAE 0.842948718 |

Kev has 10,230 valid and 1,027 overlength receipts. Nimble has 8,006 valid, 2,253 unsupported, and 998 overlength receipts. Native limits remain Kev 8,192 state/state-plus-branch and 16,384 packed, and Nimble 2,048 tokens / 26 candidates / nonempty context. Unsupported reason precedence is preserved; a candidate-limit receipt does not establish that the same row would fit context.

Only the original E33 population was evaluated. There is no separate E33 NOTA or permuted variant denominator, and no raw-T1 panel was pre-registered or added here. Existing original candidate order is preserved. These missing variant panels must not be interpreted as zero error or invariance success.

## Flag-directed diagnosis

All flagged source/type populations were checked against original data identities and receipt status counts. The full file hash of every receipt was rechecked against each hardened audit manifest; no source run or flag was changed.

Kev cells 27 and 39 are the original `finqa-yes-no` noul population (22/22 valid, 15 correct) and `jevbench` score population (16/16 valid, MAE 0.4365375); both are below the watchdog minimum n=30. Cell 49, `longbench-retrieval-en`, has 0/200 valid: all 200 receipts report native context overflow, with recorded state lengths 10,052–15,248 >8,192. Its full-denominator accuracy is 0 and valid-only accuracy is `null`; no model output was fabricated.

| Nimble flagged cell | Source/type | Valid / full | Receipt reasons | Result / interpretation |
| ---: | --- | ---: | --- | --- |
| 4 | aida-testc / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |
| 8 | clinc150 / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |
| 20 | cuad / noul | 31/200 | native_prompt_limit_2048: 169, within_native_budget: 31 | 31/200 correct |
| 27 | finqa-yes-no / noul | 22/22 | within_native_budget: 22 | 18/22 correct |
| 29 | go-emotions / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |
| 36 | helmet / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |
| 39 | jevbench / score | 13/16 | within_native_budget: 13, native_prompt_limit_2048: 3 | MAE 0.230769231 |
| 45 | lex-glue-ledgar / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |
| 46 | lex-glue-scotus / choice | 8/200 | native_prompt_limit_2048: 192, within_native_budget: 8 | 4/200 correct |
| 48 | longbench-lsht / choice | 0/200 | native_prompt_limit_2048: 200 | 0/200 correct; valid accuracy undefined |
| 49 | longbench-retrieval-en / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |
| 50 | longbench-retrieval-en-e / choice | 0/200 | native_prompt_limit_2048: 153, native_v1_candidate_limit_26: 47 | 0/200 correct; valid accuracy undefined |
| 51 | longbench-retrieval-zh / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |
| 52 | longbench-trec / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |
| 53 | longbench-trec-e / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |
| 57 | nlu-eval-68 / choice | 0/200 | native_v1_candidate_limit_26: 200 | 0/200 correct; valid accuracy undefined |

The suspicious Nimble CUAD valid-only 1.0 rate was checked against all 31 valid receipt hashes: 29 gold false and 2 gold true, with matching returned decisions, 31 distinct probability vectors, and noul probabilities ranging from 0.0002647662 to 0.9996658564. This is a real 31/31 valid-subset result under the frozen rule, while **169/200 CUAD rows are overlength** and full-denominator accuracy is 31/200 = 15.5%. It does not demonstrate perfect full-population behavior. Small populations, undefined zero-valid cells and this exact-boundary flag remain in the artifact.

## Evidence and resource handoff

Fresh CPU-only closeout directory: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_results_closeout_20261031`. Retained container `fffd539c67f6dd655ca3373e2a5653651c8d2e2d1a10d51df7323f5b364953d2` exited 0; terminal `2026-10-30T21:49:51Z` binds 22,514 rehashed receipts. It has persistent heartbeat, log, terminal and exact launch/resume commands. This closeout verifies terminal/receipt bindings and diagnoses flagged cells; the frozen native finisher owns independent native-response reconstruction and metric arithmetic.

| Model | Inference terminal UTC | q/s/chip (1 chip) | Reserved GiB | Receipt manifest root SHA256 |
| --- | --- | ---: | ---: | --- |
| Kev-0.8B | 2026-10-30T21:17:07Z | 1.166318467 | 21.466796875 | `16ffb99c0e6988ce34be7d7d9cce2acd8cedbd0f5df3342c27fea8a7e22912c4` |
| Nimble v1 | 2026-10-30T21:46:07Z | 1.234153776 | 18.708984375 | `d062a073fd05fe18ad081b36edcdee16db535de5ea0e48a4f181797ed1345c48` |

Rates are the run-reported forward throughput per chip, not end-to-end elapsed throughput including skips and auditing. The [machine-readable result](JEVAL-REFERENCE-RESULTS-2026-10-31.json) preserves every source/type cell, flag, file hash, retained Docker identity/state/device mapping, config, report and terminal binding. Full ordered manifests remain in the original hardened audits. Closeout report SHA256: `4d81842f8748bd4337073924bf764d4a60d94db41e7925b74931574d1f57bbbe`.

Kev report SHA256 `dcee22c5848cacaa6fc6ffa394b12b79f769dc717589b92596a03e23bc2f710c`; Nimble report SHA256 `1bcf640ed9e8d02a20b03d71bcc39d0aedf27aa9a7b47e28d32d046d037693d8`.

Chip 0 (Kev) and chip 1 (Nimble) resource release is a separate parent decision requiring fresh allocation ownership and live-device checks under lock. This closeout performs no release. Kev-4B/9B JEVal results remain pending; Open-Jev JEVal remains subject to its separate admission work. No formal training, new fitting, real-business benefit or Astra approval follows from these results.

## 2026-10-31 dated clarification after actual Astra review

The original table's “2,253 unsupported” count remains correct. Actual Astra
review identified an incorrect candidate-limit-only explanation in the frozen
closeout README. Receipt-level recount splits those 2,253 rows into **2,047
`native_v1_candidate_limit_26` and 206 `native_nonempty_context_required`**;
the latter are 95 ARC-Challenge and 111 ARC-Easy rows with empty state and no
more than 26 candidates. The separate overlength count remains 998. No reported
metric, valid denominator, prediction or flag changes. All 6/30 flags and
`VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED` remain.

The actual Astra review supports bounded reference publication after this cause
clarification, with every original scope limitation retained. See
[the full review](ASTRA-JEVAL-RESULTS-REVIEW-2026-10-31.md). The original closeout
now has an additive `ERRATUM-20261031.md`; no frozen evidence was rewritten.
Erratum SHA-256: `73a81a296f3dc39acd61303023b671e2bea7f8ff342b33c8002db537d5781015`.
