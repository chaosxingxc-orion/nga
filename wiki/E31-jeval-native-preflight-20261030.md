# E31 — Full JEVal native eligibility

## Purpose and hypothesis

Defects 12/16: preserve all 11,257 row identities and native protocol limits. Gold-input invariance has candidate content/order discrimination counterparts. Token eligibility is not correctness or consistency.

## Setup

[Pre-registration](../experiments/JEVAL-NATIVE-PREFLIGHT-2026-10-30.md). Six existing <10B reference checkpoints; CPU only, exact JEVal parquet, native unextended budgets and original state strings. Unsupported and overlength rows remain in complete counts.

## Execution

Retained detached CPU containers on 175 using existing immutable image, complete frozen dependencies, CephFS per-item receipts, logs, heartbeat, terminal and exact guarded relaunch. No NPU allocation or weight updates. Purpose/setup are recorded before launch.

## Results and verdict

Pending. Adapter tests and CPU eligibility do not establish model test performance.

Execution update: ten CPU mapping/eligibility tests pass, including original
JSON-looking state preservation, gold/metadata isolation, candidate discrimination,
Nimble 27-candidate rejection before tokenization, native overflow classification,
and rejection of unrelated native errors. Actual parquet inspection confirmed
`questions_json` / `label_json` storage columns. The initial unlaunched preparation
was archived before fixing that column binding; no running snapshot was edited.

All six retained CPU containers have now actually launched, no NPU devices and
2-CPU limits. Output directories are `reference_inference/jeval_{kev08,kev4,kev9,
openjev2,openjev9,nimble}_preflight_20261030/`. Exact launch receipts bind image,
command, configuration and wrapper. Frozen file counts: 67/72/70/87/90/138.

| model | container ID | config SHA256 |
| --- | --- | --- |
| Kev 0.8B | `e6461a2b7a1071daaa080ebb1e9098b35e4275c4e91cbaf399ef7e42989d6dec` | `09774f19553b47a2ca5104138d2dcbbdce442131c1435c8ee8cd1a8a8baf7c70` |
| Kev 4B | `d0340fd6187fccd6de71b7a5ba8390be9dcb9028d4aa4f6199c0cb7d0685d432` | `9f714bed9c99eaad4397b7b82f102492eaac8d44a70136e5a8a697d82eaab8e7` |
| Kev 9B | `fac1114312b7c69299a30d723020b3f5bc6a1299475dd68d66c53e1dfc42852c` | `08a063f3eddbaf68ad5724498099323c21c9f7e7352af1788947d32e3c614d46` |
| Open-Jev 2B | `670606cad135086522a7f8908993cef4d5b357e398d6fe0804d912bcc3212940` | `7a300c5b966d88933e9bde13bb4902e5bbcf25a70f17ad4eaeefe8155e462149` |
| Open-Jev 9B | `ac85195a5eb5067b3a2102e0580ad446cff0754b4630ac25ba345ee370598904` | `96da6a7593514047c8499795df15ed058de5ce1fbbd5b4d001d0550131f5e595` |
| Nimble initial | `29fbdb38d3e6a412f5576b356718d915b009a7cabdf84d93f36a0606976e41cf` | `4e1614698ef49d27a911c0847965bcdb061ffaa0f6a3eb7aaf602ab42fb85e64` |

At the first actual-container check all six were running; Kev 0.8B and Open-Jev
2B had entered token eligibility, others were verifying dependencies. Full counts
remain pending; startup or a token prefix does not establish full eligibility.

2026-10-30 correction: initial Nimble exited 1 at 201/11,257, with
`ValueError: Context must be a nonempty string.` The failed row has exactly empty
state, and native `parallel_schema.py:87–90` rejects this. A separate CPU inspection
found 206 empty states in the full population. The dated pre-registration amendment
classifies these native incompatibilities as unsupported without fabricated text;
candidate-width rejection has precedence. A fresh v2 configuration/run will retain
v1 evidence untouched. Twelve mapping tests now pass, including empty/whitespace
state and width-before-empty precedence. The three Kev CPU runs completed all
11,257 rows with actual Docker exit 0; their independent artifact audit is pending.

Nimble v2 actually launched at `2026-10-30T18:09:51Z` in
`jeval_nimble_preflight_20261030_v2/`, container
`47e7e34e2ec81bdf83fce44d4791c9524308c506de13b18265d23e20dccb61d3`,
config SHA256 `9afdd2b309b7f5f07e0b2a438a2f997a18f60ba75dc4c2f137e6bb304f455e00`.
Its initial verification and subsequent progress are observed in its own digest.

The three Kev reports each count 10,230 eligible and 1,027 overlength rows:
choice 8,625/957, noul 1,286/70, score 319/0 (eligible/overlength).
Identical counts triggered the required suspicious-success check. All three
frozen configurations bind identical `tokenizer.json`, `tokenizer_config.json`,
`kev/api.py` and `kev/model.py` hashes, so equal token eligibility is expected;
weights play no role in this experiment. This does not establish equal model
performance. A separate artifact audit checks every original parquet row and
receipt hash, complete counts, config/dependency hashes, report hash, and retained
Docker/terminal/wrapper evidence; it does not independently retokenize.

The independent Kev artifact audit completed at `2026-10-30T18:12:37Z`,
three runs/all 33,771 receipts passed. Evidence is
`reference_inference/jeval_artifact_audit_kev_20261030/` (`report.json`,
`COMPLETE.json`, `EXIT`, captured `docker-states.json`); the retained audit
container also exited 0. Each model's eligible/overlength sequence has the same
hash, consistent with the frozen native tokenizer/encoder identity above.

Nimble v2 completed all 11,257 rows at `2026-10-30T18:13:44Z`, actual Docker
exit 0 and terminal rc 0. Its report counts 8,006 eligible, 998 overlength,
2,253 unsupported (2,047 candidate width + 206 empty context; no overlap).
By type, choice is 6,512/817/2,253, noul 1,182/174/0, score 312/7/0
(eligible/overlength/unsupported). Separate independent artifact audit pending.
The failed v1 remains retained as evidence of the amended compatibility rule.

Nimble v2's independent artifact audit subsequently passed at
`2026-10-30T18:14:54Z`, all 11,257 original row/receipt identities, frozen inputs,
and terminal/report/actual Docker bindings. Audit evidence is
`reference_inference/jeval_artifact_audit_nimble_20261030/`; audit terminal and
actual container/wrapper all exit 0.

As of `2026-10-30T18:14:47Z`, Open-Jev 2B/9B remained genuinely running at
6,623/6,620 rows. Their helmet segment contains hundreds of candidate prompts per
row and is slower; observed per-item receipts include 150–220 candidates and
maximum lengths above 10,000 tokens. Native exact enumeration is retained, without
changing the frozen protocol or treating a slow row as a failure. Their final
eligibility totals and audit remain pending. No six-model inference-result table
can yet be inferred from this eligibility experiment.

### 18:21 UTC independent audit correction

The earlier artifact auditor checked every listed hash but did not independently
enumerate the required dependency closure or pin the dataset hash and terminal
total. The hardened auditor adds those checks, unique original IDs, native
unsupported/length reason consistency, maximum-length aggregation and report →
terminal → wrapper chronology. Seven focused negative tests pass. It still does
not independently retokenize.

A fresh detached audit of the three Kev populations and Nimble v2 completed at
`2026-10-30T18:21:04Z`, all 45,028 receipts accepted. Required files independently
enumerated: 67/72/70/138. Counts remain unchanged. Evidence directory:
`reference_inference/jeval_artifact_audit_hardened_20261030/`; container
`f9b5cbee9af63b9b5c3a714f28e6fd11ff914193d48736a58b32c55f15fabe44`.
Report SHA256: `64ad893c26b86c66bf50436ab6bf9345ab4f0840dde471dadeaed6e08d984c5d`.
Terminal, wrapper and retained audit container exited 0. After completion,
the four original container identities/configurations and exited/0 states were
checked again against the captured Docker snapshots; audit source hashes and
launch binding also remained intact. Earlier audit evidence is retained.

### 18:42 UTC Open-Jev completion-audit setup

Both original Open-Jev token-only containers are still running (18:41 UTC:
about 9,420/11,257 rows). A separate retained CPU waiter will preserve those
runs and wait for both actual Docker exited/0 states and successful bound
terminals. It will then capture fresh Docker snapshots and run the hardened
independent artifact auditor against all 22,514 receipts. It checks the actual
container identities again after audit; no model forward or NPU device is used.
Output: `reference_inference/jeval_artifact_audit_openjev_20261030/`.
Purpose/setup precede launch. Pending results are not eligibility totals or scores.

The Open-Jev artifact waiter actually launched at 18:42 UTC, retained CPU
container `51f52b4afecf078396a1228c83e30b2ec6a370f5b1be33e64662da7e52171758`.
At 18:42:46 UTC both original preflight containers remained running at
9,445/11,257 and 9,448/11,257; the waiter was running. It does not restart either
preflight. Complete audit and eligibility totals remain pending.

### 18:52 UTC completion verified by parent

Both Open-Jev preflights completed all11,257 rows at18:43:28/18:43:34UTC.
For each:9,704eligible /1,553overlength /0unsupported. Bytype choice8150/1432,
noul1235/121, score319/0 (eligible/overlength). Full artifact audit of22,514
receipts completed18:44:48UTC, exact dependencyclosure87/90files; report SHA256
`626baa8220d1ddd8b85f57f22cf590b71dc43940ed928b7d4775c90b4324c212`.
Parent read report and terminal/wrapper and rechecked original+audit actual
container identities and exited0. Scope remains artifact/identity/length
classification, not independent retokenization or model performance.
Both status sequences match
`ff4efe7936ceeb70aba8870432828d9bb4aea0724c68c52fd429896b43cf15c3`;
identical eligibility must not be interpreted as identical model quality.
All six checkpoint eligibility populations are now complete.
