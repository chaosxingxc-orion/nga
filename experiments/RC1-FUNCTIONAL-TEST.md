# RC1 fixed-roster converted same-TEST measurement contract

Status: **SCOPE AND METRICS FROZEN — EXECUTION ATTACHMENT PENDING**. Frozen2026-11-06 before this campaign's DEV results, following bounded Astra planning review. Exact adapter/publication/run pins and actual evidence receipts must be attached before execution. This text authorizes no data read, launcher, FINAL or ticket by itself.

## 1. Prospective scope amendment

This is a new descriptive measurement contract for eight already fixed RC1 training lanes. It imports the named Track K arithmetic and controls from S (`R3-SFT-PREREG.md`), W (`R3-TRAINING-WAVE-PREREG-2026-10-31.md`) and the accepted November5 same-TEST report, but does not import their model selection/adoption verdicts or seven-member 0.8B membership. It does not amend their historical outcomes. The November5 scale-reuse draft concerns different old artifacts.

The evaluation inventory is fixed regardless of future DEV/TEST values:

| Size | Adapter seed2 | Adapter seed3 | Own untrained comparison |
| --- | --- | --- | --- |
| 0.8B | RC1 Base0.8B terminal3116 | RC1 Base0.8B terminal3116 | Exact matching Qwen3.5-0.8B-Base |
| 2B | RC1 Base2B terminal3116 | RC1 Base2B terminal3116 | Exact matching Qwen3.5-2B-Base |
| 4B | RC1 Base4B terminal3116 | RC1 Base4B terminal3116 | Exact matching Qwen3.5-4B-Base |
| 9B | RC1 Base9B terminal3116 | RC1 Base9B terminal3116 | Exact matching Qwen3.5-9B-Base |

Model-of-record is Base plus unmerged published terminal adapter. No step3000, alternate seed, old adapter, best size or best checkpoint substitution. Each Base is a single checkpoint, not a trained seed. Extra QO/PT, Instruct, challenger or 27B members are not part of this inventory. Historical panels may be linked as separate context.

Before launch, bind each lane's exact base revision/inventory, tokenizer, adapter payload/publication and training terminal, seed, recipe, evaluation code/image/config and output directory. Attach existing RC1 training lineage including two-step smoke/resume as actually recorded. This evaluation cannot retrospectively certify training provenance that is absent.

## 2. Objective, defects and falsifiers

Measure held-out public-task performance of these fixed artifacts and their own-Base differences under a common continuation readout. This serves defect12's measurement prerequisite; it does not clear the G1 consistency gate. Accuracy and level/probability diagnostics contextualize defects1/17 and ordinal strata8; permutation targets6; NOTA/operator/probability context targets5/16.

Lookup by source/question and input neglect can maximize apparent accuracy. Ignoring inputs/names can yield zero permutation flips. Always/never-NOTA can win one NOTA side. Gold lookup minimizes Brier/NLL; constant calibrated confidence can minimize ECE. Therefore report constant/uniform/drop/blank, paired permutation correctness, NOTA both-sides-right and clean accuracy alongside these measures. No aggregate accuracy is called consistency. Trained permutation is a sanity check, not untrained invariance. No semantic-transfer, adoption, G1/G2/G3, strict Kev reproduction, scaling-law or business-readiness claim is made.

## 3. Frozen populations and access

Use the exact historical converted populations, with metadata pins copied below from accepted sources rather than newly opened payloads:

| Population | Clean n | SHA256 |
| --- | --- | --- |
| decision-v7 calibration | 1148 | c3eeeda72740fbde6fbcc28e1dff0928c98407242543d0bd8f0819497f502b69 |
| decision-v7 TEST | 1200 | 55e21d63b93550ff2e1c98b32c2be558af02bde31c0633f8448d8f38d23fe1b2 |
| transfer-v4 TEST | 656 | 43de4b7d6efb2d4b6b78b670ba82b98fefa324076fdda1b0462f5902ac02f7fc |
| decision-v7 TRAIN, constant fitting only | 15576 | 5ddc8e94f3e0af1c8abdb887ed77c1e8813879efcc428edc6d4ea0bed537daf6 |

Retain manifest SHA256 `c2e8cbc6e0c686be2cc730890928d803e3f4de1b9b745abbea90adb6f3903afd` from W, subject to verification against the accepted closure. Copy exact TEST variant hashes and file paths from that frozen manifest into the execution attachment before launch; do not generate variants afresh. A changed identity requires resolution before reading/scoring, not acceptance because counts happen to match.

S fixes decision TEST96 permuted and72 each NOTA-present/absent (240 variant rows), transfer TEST36 of each (108). These count expectations must agree with the bound manifest. No new outcome-based filter. Each adapter has nine readout groups: decision calibration clean; clean/variants/drop/blank for each TEST suite. Expected question-condition total per adapter is1148 + 3×1856 + 348 =7064; eight adapters56512, of which14848 are clean TEST. These exclude CPU constant/uniform and any additional K0 acquisition; they are not candidate-forward counts. Reused calibration changes compute cost, not the logical population.

Freeze membership/claims and exact access configuration before opening new candidate TEST. Existing accepted public historical TEST results are known; this is a prospective new-artifact evaluation on reused public populations, not a newly pristine benchmark. Preserve old access records and prohibit TEST/report-half use for selection or tuning. One scientific evaluation per model/suite with exact-config item-level resume; interruptions do not justify reselection or a second outcome-driven run.

## 4. Instrument and execution

Use the accepted full Track K continuation instrument, numerical mode FP32, rightpad, HF32off, token-budget16384, fixed prompt/render/tokenizer/candidate order and full summed candidate continuation log probability. Token budget is a padded batch budget, not permission to truncate context. Freeze chunk/resume behavior with the actual admitted source closure. `--full --arm K1 --partitions calibration,test --stages k --scorer rightpad --dtype float32 --token-budget 16384 --no-hf32 --require-record-grade` states the intended model scoring scope; this is not a standalone authorized launch command. K0 uses its actual K0 role.

Persist the K-only returned object through the reviewed wrapper/CPU path. Do not add `report` or `t_score` flags: both reach Track T raw files in the legacy full evaluator. Probability metrics come from K score vectors on CPU. Separate pure metric computation from accelerator ownership. One practical bundle load per model; retained detached container, durable log/heartbeat/terminal marker, item resume and exact relaunch command. Report per-chip throughput with chip count/reserved memory and wall time under the existing measurement conventions, without making speed a new scientific eligibility threshold.

Validate identity, complete ordered keys, candidate dimensions/order/gold, finite scores and terminal/publication binding before accepting metrics. An OOM may change resource assignment under a documented protocol-preserving plan; it cannot silently change precision, length, population or candidate checkpoint. Bind source image digests despite the single release name.

## 5. Metrics, calibration and controls

For every fixed member and each suite separately report n, correct, first raw-score argmax accuracy, R0 tie-as-incorrect accuracy, exact top ties, source/type strata, near-tie census at1e-3 nats and10×/100×, gold-position distribution, duplicate candidate/token audits and vacuity. Singleton rows are retained. No dropped invalid rows; missing/invalid populations make the panel incomplete.

Retain CPU constant fitted on TRAIN with question/position/position0 tiers; uniform; same-model input-drop and input-blank. No trained-QO inference from these transforms. Historical K-floor values may be labelled as diagnostic predicates on current DEV, never used to select this inventory.

Full Track K secondary metrics are frozen by `variants_r3.py`: permutation same-order exclusions and tied-pair drops counted, ID flip with both-correct denominator and all-permuted-row accuracy; NOTA absent selection, present accuracy/false NOTA and both-sides-right under both tie conventions. No change to their denominators or a new pass-all gate.

Fit operator tau per model only on calibration1148 using the unchanged R0 grid0.50:0.05:0.95, utility+1/−1/0, higher-tau tie break, minimum20 and source-keyed fallback tiers. Persist its fit and apply unchanged to both TEST suites. Use exact accepted DEV calibration readouts if the same model/instrument binding is established; otherwise acquire the registered calibration under the frozen TEST instrument, without changing the rule. Transfer uses default0.5 under this implementation. Operator accuracy/C are harness columns, separate from Kev and probability calibration.

T=1 probability panels follow `R3-REFERENCE-METRICS-SUPPLEMENT-2026-11-01.md` and its conventions clarification exactly: binary64 stable softmax; stable unclipped NLL; Brier summed over options and averaged over questions; ECE10 with raw-score correctness and binary64 edges i×0.1 plus exact1.0. Lower-inclusive bins, final upper-inclusive; count/mean confidence/mean correctness/contribution, empty means null. Report probability-argmax mismatches and exact ties. No fitted temperature, clipping, probability floor, score length normalization or mask change. Each seed and distinct K0 has its own panel; no ensemble probability panel or pooled cross-suite/seed metric.

## 6. Own-Base comparisons and uncertainty

Before declaring a matched effect, bind exact same-size Base bytes, population/order, candidate/gold, tokenizer/prompt/continuation scoring and numerical mode. Existing K0 DEV acceptance does not authenticate K0 TEST. Reuse existing accepted TEST vectors only with applicable provenance and runtime evidence. Historical8190/current4726 metadata similarity alone is insufficient. Reuse accepted equivalence evidence if applicable; otherwise resolve only the identified gap with a bounded predeclared DEV bridge under existing tolerances, or obtain the needed K0 under the same admitted inference runtime. Do not rerun all external references.

For each of four sizes and two suites, report both seed effects and the two-seed average:

`d_q = (I(seed2 correct on q) + I(seed3 correct on q))/2 - I(Base correct on q)`.

Report paired discordants per seed and separately count positive/negative/zero mean differences. For each comparison use the pinned historical `paired_bootstrap`: reset NumPy default_rng(20261030), 10000 sequential draws of n indices with replacement using `rng.integers(0,n,size=n)`, mean(d) per draw, linear percentiles at the original function's `[100*(1-.90)/2,100*(1+.90)/2]`. Respect source question ordering. Use n1200 or656, never pooled1856 or seed-question rows. Report per-seed descriptive intervals the same way, with distinct labels. Percent-point differences and intervals use explicit units.

These are conditional question-level descriptive intervals. They are not record-cluster, random-training-seed, multiple-comparison or universal-success inference. W §5 point criterion is reported as a **descriptive historical-criterion indicator** per complete size: at least+1 pp on one suite, no worse than−1 pp on either, exact rational boundary comparisons and both intervals. It is not selection, adoption or a new CI gate. An interval spanning zero is inconclusive for a positive difference. All sizes/suites appear whatever the indicator. No “best size” or family-wide significance headline.

If a Base comparison is not authenticated, report the adapter's valid standalone metrics and mark the effect unavailable/runtime-confounded; do not subtract unlike metrics as a training effect. That leaves the intended complete own-Base comparison objective unfinished.

## 7. References and explicit exclusions

The accepted November5 `reference_mapping_addendum` authenticates the1856-question converted/source data mapping and masks. Reuse it conditional on exact matching bytes; retain interface, whitespace, checkpoint, runtime and historical audit-terminal limitations. It does not equate pointer heads with continuation scoring or prove original labels/leakage status.

Local reference native temperature and T1 stay separate. The recorded0.8B native value2.3510958125672174 is not a default for every reference. Require matched populations/masks/gold/ordered options and formulas; distinguish probability-first-argmax reference accuracy/ECE from raw-score correctness unless the item predictions agree. Published aggregates permit aggregate context only; no paired loss inference without matched item losses. Other public suites, masks, soft-gold losses, endpoints and reference families have their own protocols. No synthetic Kev2B counterpart.

Track T is **out of scope**. A future T1/T2/T3/B1–B4 report requires a separate frozen protocol with exact raw sources, selection/report split, tau carve-out, minimum cells, R0 tie/null conventions and B1/B2/B4 admissibility. It cannot be enabled as a formatting step, used to retrospectively select these adapters, or described as passing G1/G2. The current Track K reference-alignment objective does not need that extension.

## 8. Failure handling, evidence closure and publication

Actual DEV/calibration completion and source/numerical review establish instrument readiness; no favorable threshold is required for inclusion. Missing or failed training/publication/DEV measurement keeps a named failed/unavailable roster row and cannot be replaced. Valid other lanes may proceed once their own evidence and shared instrument are ready under this frozen rule. A missing seed forbids a two-seed mean or success for that size; partial work is labelled partial. Adverse semantic controls restrict interpretation and remain in the report. Instrument errors require repair before valid measurement, retaining the old failure record and exact reason; outcome values cannot determine a repair or exclusion.

Before launch, attach: (a) eight-role roster and exact available publication pins; (b) actual DEV nine-group counts, terminal and consumer review with adverse findings; (c) exact source/config/data/control/metric pins and K-only reporting path; (d) per-size Base reuse/acquisition/runtime evidence decision; (e) immutable launch/access/resume configuration. Review these concrete artifacts under existing release controls. No currentDEV acceptance or launch approval is asserted here.

After inference, CPU reconstruction binds exact keys/gold/candidates/scores, full metric populations, controls, tau and effects to model/config and actual completion. Independently review the numerical results and exact run artifacts with Astra before public conclusions. Publish all roster statuses, all registered panels and limitations. Preserve accepted historical results and dated corrections; update latest links without silently rewriting history.
