# E31 — JEVal native input eligibility before reference inference

Pre-registered 2026-10-30 before E31 execution. Defects 12/16: preserve exact task identity and measure interface/length eligibility. A constant or gold-leaking predictor is a degenerate optimum; this token-only experiment does not measure model quality. Gold/metadata input invariance is paired with candidate order/content discrimination. Unknown encoder errors fail the run rather than being called unsupported.

Population: exact `carlosxiang__JEVal/data/test.parquet`, SHA256 `88f090a510e511d1236fdf5ddb428a8b965663ff0cc1061f950b88f0c99d2e82`, all 11,257 ordered rows/one question each (9,582 choice, 1,356 noul, 319 score). Preserve original state as a string even when it looks like JSON; decode questions only. Labels and metadata never enter the request. Preserve both dataset test identity and original source_item_id split provenance; no filtering train/dev-origin records.

Six fixed reference checkpoints match E26/E28/E29: Kev 0.8B/4B/9B native pointer schema, Open-Jev 2B/9B native independent candidate prompts, initial Nimble v1/9B full supplied one-question schema. No weights are loaded or trained. Native budgets: Kev state 8,192 / state-plus-branch 8,192 / packed 16,384, strict; Open-Jev 4,096 per candidate; Nimble 2,048 per prompt with at most 26 candidates. No truncation, candidate clipping, prompt changes, or adoption of the paper's extended budgets/windowing.

Each row receives exactly one status: eligible, unsupported native candidate width, or overlength. For initial Nimble, >26 candidates is unsupported before tokenization; these 2,047 known rows do not receive fabricated length or probability values. Native overlength exceptions preserve their actual message/count; unrelated exceptions fail the experiment. Counts by type retain all 11,257 rows. Per-item records bind index/ID/raw-input/request/config hashes, native candidate order and token hashes/lengths where available. A failed run retains its valid item receipts and resumes only from a guarded exact container/config identity.

Six CPU-only retained detached containers run on 175 with existing immutable image and no NPU devices, at most two CPU threads each and tokenizer parallelism disabled. Freeze exact scripts/tests/protocol/data and full base/checkpoint/native-code dependency closure before launch. CephFS logs, timestamped heartbeat/digest, terminal, wrapper exit, launch receipt and exact resume command survive disconnects. Whole-population report requires all IDs, item hashes and statuses, immutable inputs before/after, successful terminal and retained Docker exit. Any CPU eligibility success is not model inference, JEVal scoring reproduction, training gain or Astra approval. Formal inference and scoring conventions will be separately frozen after eligibility is known.

## 2026-10-30 amendment, before Nimble v2 execution

The initial Nimble run failed after 201 receipts on row index 201,
`jeval:ai2-arc-challenge:000001` (`ai2-arc-challenge/test/14`), because its original
state is the empty string. The native `parallel_schema.py:87–90` explicitly rejects
contexts whose `strip()` is empty. A separate CPU parquet inspection found 206 such
rows, all exactly empty. This is a native interface incompatibility, not a length
failure. In a new v2 snapshot, classify these rows as `unsupported` with reason
`native_nonempty_context_required`, without injecting a placeholder or modifying
the original state. Candidate width >26 still takes precedence, so overlapping
incompatibilities have exactly one receipt/status. Other unexpected exceptions
still fail the run. Preserve the failed v1 directory, container, terminal, logs,
and configuration unchanged; v2 starts a fresh receipt population with a new
configuration binding. The other five frozen runs remain unchanged. This amendment
does not authorize inference or change any scoring convention.
