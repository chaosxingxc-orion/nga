# E33 — Kev-4B / Kev-9B JEVal native reference results

2026-10-31 dated addition to the existing Kev-0.8B/Nimble result snapshot. Both checkpoints completed the original **11,257** JEVal rows, native independent scoring and hardened audit, with all retained inference/finisher/hardened containers actually exited 0. A fresh detached CPU closeout rechecked **22,514** receipts and input/payload hashes. The status remains **`VERIFIED_HARDENED_SCOPED_REVIEW_REQUIRED`**, with **8 Kev-4B flags and 7 Kev-9B flags**. The older actual Astra E33 review applies only to Kev-0.8B/Nimble; it is not approval of these newly completed sizes.

The [E33 protocol](JEVAL-REFERENCE-INFERENCE-2026-10-30.md) remains normative. Defects 12/16 concern identity, measurement and external generalization. Dropping unsupported/overlength rows is the degenerate way to improve apparent accuracy; the complete-denominator counterpart keeps all original rows. No metric, split, temperature, threshold or prediction was selected or changed after the run.

## Native metrics and denominators

| Model | Native temperature | Correct / full classification | Accuracy | Raw summed Brier | ECE10 | Native score MAE | Flags |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kev-4B | 2.40605007216 | 6,741/10,938 | 61.629183% | 0.436118754 | 0.173661124 | 0.914080878 | 8 |
| Kev-9B | 2.19364995939 | 6,931/10,938 | 63.366246% | 0.406847145 | 0.109838099 | 0.923336991 | 7 |

For each model, classification accuracy uses all **10,938** choice/noul rows. Both have **9,911 valid classification**, **319/319 valid score**, **10,230 valid overall** and **1,027 overlength**. Ineligible classification rows remain wrong in the full denominator; Brier/ECE use only 9,911 valid classifications. Native limits are state/state-plus-branch 8,192 and packed 16,384; no overflow row is silently truncated or replaced.

Brier sums squared errors of the native returned probability vector without renormalization; noul reconstructs `[1−p,p]`. ECE10 uses native returned choice confidence (chance-adjusted for Kev), selected binary probability for noul, and `min(floor(10c),9)` bins, putting exact interior boundaries in the upper bin. Kev native wire probabilities and expected score are rounded to four decimals. Score MAE compares the returned expected level with gold in original level units; it is not argmax grade, rounded integer, or K−1 normalized error. These are disclosed local response-formula conventions; the original paper scorer is unavailable.

| Model / type | Full n | Valid n | Correct / native MAE |
| --- | ---: | ---: | --- |
| Kev-4B choice | 9,582 | 8,625 | 5,640 correct |
| Kev-4B noul | 1,356 | 1,286 | 1,101 correct |
| Kev-4B score | 319 | 319 | MAE 0.914080878 |
| Kev-9B choice | 9,582 | 8,625 | 5,825 correct |
| Kev-9B noul | 1,356 | 1,286 | 1,106 correct |
| Kev-9B score | 319 | 319 | MAE 0.923336991 |

## Retained flag diagnoses

All flagged source/type populations were checked against original rows and the complete hashed receipt manifest. The native finisher's zero overall flags does not erase hardened subpopulation flags.

| Flagged source/type | Kev-4B | Kev-9B | Interpretation |
| --- | --- | --- | --- |
| finqa-yes-no / noul | 18/22 correct | 19/22 correct | Both full and valid populations below 30; two flags/model |
| helmet / choice | 50/50 valid correct, 150 overlength | Same | Full-cell accuracy **50/200 = 25%**, not perfect full-population behavior; 50 distinct probability vectors/model |
| jevbench / score | 16/16 valid, MAE 0.296950 | 16/16 valid, MAE 0.26825625 | Small full and valid populations; two flags/model |
| longbench-retrieval-en / choice | 0/200 valid, all overlength | Same | Full-cell accuracy 0; **valid-only accuracy null**; no model predictions for this cell |
| longbench-retrieval-en-e / choice | 100/100 valid correct, 100 overlength | Not an exact-one flag | Kev-4B full-cell accuracy **100/200 = 50%**; 100 distinct probability vectors |

Helmet overflow state lengths span 10,431–15,413; retrieval-en spans 10,052–15,248. Kev-4B's flagged retrieval-en-e excluded rows span 8,260–15,001. The observed perfect rates apply to valid subsets, and flag diagnosis does not establish absence of training overlap or broader generalization. All original flags and complete 66-cell summaries remain in the [machine-readable evidence](JEVAL-KEV4-KEV9-RESULTS-2026-10-31.json).

## Execution evidence

Inference terminal UTC: Kev-4B **22:27:37**, Kev-9B **22:28:08** on 2026-10-30. Native finisher terminal UTC: **22:28:50 / 22:29:35**. Hardened waiter terminal UTC: **22:30:19 / 22:31:50**, with actual Docker exited/0. Their last progress digests still say `hardened_audit`; those progress strings do not override successful terminal and actual exit records.

The fresh closeout `nga-jeval-kev49-closeout-20261031-v2` ran detached without NPU devices, original CephFS read-only, only its own output writable, and Docker socket reads restricted in code to HTTP GET inspect. It completed **22:39:12 UTC**, 22,514/22,514, actual container ID `888d0434d62f23418e15cca2d33327ccc48751895bd18a902acf9b816e30122e`, exited 0. It verifies all receipt file hashes against the hardened manifests, ordered original Parquet identities and payload/input hashes, report/config/audit/terminal bindings, flagged-cell status/reason counts, and retained Docker ID/image/command/wrapper/exit. Native response reconstruction and metric arithmetic belong to the original independent finisher; the closeout does not pretend to rerun external weights or independent retokenization.

CephFS evidence: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/jeval_kev49_closeout_20261031_v2/`. Closeout report SHA256: `8d2af0809eda8d1c7772051b33b91bb30e864fae8d972c119810109417de0649`. Exact launch/resume scripts, ten-second heartbeat, per-item hash journals, terminal and wrapper EXIT are retained. Earlier rejected preparation did not launch a container or delete original evidence.

| Model | q/s/chip | Chips | Reserved GiB | Receipt-manifest root SHA256 |
| --- | ---: | ---: | ---: | --- |
| Kev-4B | 0.892280268 | 1 | 55.201171875 | `5b296ba329b5acb2af836bd6ede8622f47bdf06a9d82be9f433d814f476dcec5` |
| Kev-9B | 0.864467815 | 1 | 51.357421875 | `f8964dfe5346d4e654a34de304dbdba358fbb90745b241b1dc7a5005539318f2` |

These are run-reported forward throughput observations, not end-to-end audit-inclusive throughput or fair cross-interface efficiency rankings. No chip was released by this closeout.

## Claim boundary

These are local native-budget reference measurements on the original JEVal population. They do not establish exact paper-scorer reproduction, source-macro performance, paired consistency, raw-T1/NOTA/permuted variants, training gain or real-business benefit. Different reference checkpoint sizes are not a Jev before/after training comparison. Actual Astra result review for these two newly completed models remains pending.
