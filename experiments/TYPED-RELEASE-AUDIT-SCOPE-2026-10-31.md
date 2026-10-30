# Typed Decisions: bounded result-release evidence

Prepared 2026-10-31 (Asia/Shanghai). This is an evidence inventory for a pending result-release review, not a review verdict, a new preregistration, or a training-benefit claim.

## Snapshot

Bundle: `/mnt/cephfs/xingchao/experiments/jev/reference_inference/astra_reviews/typed_results_candidate_20261031`.

The bundle contains 2,547 manifest-listed files, 19,686,795 bytes, plus `MANIFEST.json`. It includes six complete 400-receipt sets, the original configs, reports, preflight/probe metadata, terminal markers, finisher audits, recorded inference-container exits and small verifier/source documents. No weights or model execution are included.

`MANIFEST.json` SHA-256: `799243b7b91a937ac50840896f3c1f2b1f04c9ca1944c79177d5f8a503765c71`.

Canonical file-list SHA-256 (stored as `meta.manifest_sha256`): `28da3706a1913cfe3774c4e3af31004c03f8cb8e0c4bbbbccd5a16f36c410a10`.

## Checks actually completed

- A short retained CPU-only container, `nga-typed-release-extract-20261031` on server 175, extracted all 400 public test rows using the fixed image `sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`. Container ID: `8897a3a24b1928ce85cc858af502a99c08e9976a3235cfdc0fc96b4387482616`. It mounted only the bundle, no devices or weights, and its actual Docker exit code was 0. `EXTRACT_COMPLETE.json`, `EXTRACT_EXIT`, and `EXTRACT_CONTAINER_EXIT.json` retain the evidence.
- The frozen parquet SHA-256 is `4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`; the order-preserving extracted `data/rows.json` SHA-256 is `2f76c4a7e72692e7de3750fdb6dd9ba2c5566d6dc672b0d95c0c7e036a467f35`.
- `recompute.py` is a separate standard-library implementation. It imports neither production inference code nor existing verifier code. It checks exact receipt filenames and coverage, per-family receipt/config/input hashes, question and candidate order, finite logits and valid probabilities, logits-to-probability agreement, report/audit/terminal bindings, and independent arithmetic for all 11 serving/raw-T1 panels and their type/workflow cells.
- The final bundle was rechecked with `recompute.py`, and its output matched `RECOMPUTED.json` byte for byte. Status: `BOUNDED_ARITHMETIC_AND_BINDINGS_VERIFIED`; six models, 2,400 receipts, 11 panels. Existing finisher audits remain `VERIFIED_SCOPED`, with 400 rows, 2,000 questions and no review flags each.

| Model | Serving hard-argmax accuracy | Question denominator |
| --- | ---: | ---: |
| Kev-0.8B | 45.95% | 2,000 |
| Kev-4B | 66.45% | 2,000 |
| Kev-9B | 68.05% | 2,000 |
| Nimble-9B | 65.10% | 2,000 |
| Open-Jev-2B | 58.25% | 2,000 |
| Open-Jev-9B | 67.80% | 2,000 |

## Formula and scope boundaries

Each question is equally weighted: choice 600, noul 600, score 800. Accuracy compares first argmax to first gold argmax. KL is gold-to-prediction with a `1e-9` prediction floor. Brier sums squared distance to the soft gold distribution. ECE10 uses hard argmax correctness. Gold's rounded probabilities are not renormalized; predictions are normalized as in the public arithmetic.

Serving and raw-T1 panels remain separate. Kev receipts contain temperature-scaled logits, so the raw panel first recovers raw logits using the frozen temperature. Open-Jev receipts already contain raw logits. Nimble's native temperature is 1, so it has one panel.

This check does not reload weights, rehash the full external dependency tree, independently re-tokenize, or rerun inference. It does not newly inspect the six original inference containers: it binds their previously recorded exit evidence through the finish-marker hashes. The original Kev audit binds token provenance but does not independently re-tokenize or fully validate wire answers; Nimble/Open-Jev audit scopes state independent prompt reconstruction and wire checks. All original scope text is preserved in the bundle and `RECOMPUTED.json`.

A successful bounded arithmetic check supports review of the saved result evidence. It does not establish hardware equivalence, full original wire/HTTP scorer equivalence, training benefit, business benefit, or permission to start formal training. **An Astra result-release verdict has not been produced by this preparation task.**

## Reproduce the bounded check

From the bundle directory:

```sh
python3 -P recompute.py . > /tmp/typed-recomputed-review.json
cmp /tmp/typed-recomputed-review.json RECOMPUTED.json
```

Keep output outside the bundle so the final manifest remains unchanged. Further review may inspect the bounded snapshot and source documents; any substantive finding should cite file and line evidence rather than treating the existing audit status as a release verdict.

## 2026-10-31 dated addendum: actual Astra review completed

The earlier statement that this preparation task had not produced an Astra verdict describes the preparation cutoff and is preserved above. A subsequent actual read-only `gpt-6-astra` CLI review completed at 2026-10-30T21:13:39.528282+00:00, with runner rc=0 and actual child wait return code 0. Its original review SHA-256 is `e4330a6892011ba8ff85a2ea2dbd3f80453dda32e31adcef9d10d53c8fad2052`. See the [full review and evidence bindings](ASTRA-TYPED-RESULTS-REVIEW-2026-10-31.md) and [JSON record](ASTRA-TYPED-RESULTS-REVIEW-2026-10-31.json).

The review found no blocker to the limited saved-reference-metric claim. It independently checked all 2,400 receipts and 11 panels; its separate arithmetic yielded 1,485 scalar comparisons with maximum absolute difference 9.992e-16. Limitations remain: Kev wire is not original-scorer-compatible; token/wire audit independence differs by family; copied inference exit evidence does not independently prove the finisher containers' Docker exits; full external dependencies and Parquet semantic decoding were not independently rerun by Astra. The unexplained bundle metadata hash is a canonical file-list hash, not the manifest file hash; the record above supplies that clarification without changing the frozen evidence. No training/business benefit or training-launch permission follows.
