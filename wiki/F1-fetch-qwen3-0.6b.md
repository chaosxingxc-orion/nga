# F1 — fetch `Qwen3-0.6B`, the attention-only control

> Status: done · Round: R0 (unblocks R0-4 / task T4) · Date (UTC): 2026-10-30
> Pre-registration: none (an engineering fetch, not a measurement) · Run dir:
> `/mnt/cephfs/xingchao/experiments/jev/fetch_qwen3_06b/` · Code: `scripts/fetch.py` in that dir,
> using `/mnt/cephfs/xingchao/omni/manifests/jev/pdl.py`

## 1. Purpose

Restore the attention-only half of the hybrid-vs-attention control pair. `Qwen3-0.6B` is
`model_type: qwen3` (all layers `full_attention`); `Qwen3.5-0.8B` is `qwen3_5` (hybrid). Without the
pair, **defect 11** has no control, and proposal conclusion R0-4 and task T4 stay measurement-blocked
— which is how `R0-BASELINE-RESULTS.md` §8 item 5 recorded them. Feeds no gate directly; it removes a
measurement block on gate G1's task set.

## 2. Hypothesis

None. This is a fetch, not a measurement: there is no claim it could confirm or reverse. The
falsifiable part is the verification, stated before running: the local copy must match the Hugging
Face revision file by file, or it is not usable as a control.

## 3. Setup

- Source `Qwen/Qwen3-0.6B`, revision `c1899de289a04d12100db370d81485cdf75e47ca`.
- Target `/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3-0.6B/`, matching the sibling mirrors'
  convention (two-line `.complete` holding revision and timestamp).
- Through the environment's authenticated proxy (the only outbound route; a direct connection to
  huggingface.co times out). 96 workers, 1 MiB chunks, resumable per file.
- Detached per CLAUDE.md §7, with `WATCH.json`, a 30 s heartbeat carrying `bytes=done/total`,
  `run.log`, a `DONE` marker holding the exit code, and `relaunch.sh`.

## 4. Results

- 10 files, 1,519,209,243 bytes, no extra files. `DONE` holds `rc=0`.
- **Verification, three ways, all agreeing.** The two LFS files (`model.safetensors`,
  `tokenizer.json`) match the Hugging Face API sha256 values. All 10 files are byte-identical
  (sha256) to a pre-existing copy at `/mnt/cephfs/xingchao/omni/models/jev/Qwen__Qwen3-0.6B/`. The
  remaining 8 files have no API checksum and are covered by that identity plus size.
  Orchestrator spot-check: `model.safetensors` sha256 `f47f71177f32bcd101b7…` in both copies.
- Loads on CPU under transformers 5.21.0: `AutoConfig` gives `qwen3` /
  `Qwen3ForCausalLM`, 28 layers, hidden 1024, vocab 151936, `layer_types` all `full_attention`
  (the property that makes it the control). `AutoTokenizer` loads as `Qwen2Tokenizer`. No forward
  pass; model-level checks belong to T4 itself.
- **Throughput:** 38 s wall-clock, about 38 MB/s aggregate over 96 connections, about 3.6 MB/s on a
  single connection (two 8 MB range requests).

## 5. Verdict

The control checkpoint is present and verified; **defect 11 / R0-4 / T4 is no longer blocked on a
missing model.** T4 itself remains unrun.

Two recorded facts were wrong, and both are corrected in `CLAUDE.md` (commit `db5d0f9`):

1. **The model was never lost.** It was under `/mnt/cephfs/xingchao/omni/models/jev/` with a
   `.complete` marker from 2026-10-28, while the search that declared it gone looked only in
   `/mnt/cephfs/xingchao/models/jev/`. cephfs has two mirror roots; search both. The cost of this
   error was a conclusion ("defect 11 stays measurement-blocked") carried in two committed documents.
2. **The proxy is about 360x faster than recorded.** The notes said about 10 KB/s per connection;
   it measured about 3.6 MB/s. Nothing should be refused as infeasible on the old figure, and the
   figure should be re-measured rather than trusted.

This entry claims nothing about the control's behaviour. Whether the hybrid model is less accurate
than this one on low-salience bins (R0-4) needs T4 to run.

---

## Appendix: model storage consolidated (2026-10-30)

On the user's instruction that models live only under `/mnt/cephfs/xingchao/models/` and never inside
a project directory, the two mirror roots were merged:

- 33 models moved from `/mnt/cephfs/xingchao/omni/models/jev/` into `/mnt/cephfs/xingchao/models/jev/`
  (same filesystem, so a metadata-only `mv`). The unified root now holds **42 models**: the Qwen3.5
  ladder (0.8B/2B/4B/9B, each with its `-Base` variant), `Qwen3-0.6B`, and the survey's reference
  checkpoints (`jaredpalmer__kev-*` at four sizes, `ZefanCai__Open-Jev-*`, `bespokelabs__Bespoke-Nimble-*`
  and the rest).
- The 9 models that existed in both roots were verified byte-identical before anything was deleted
  (`tools/verify_model_dedup.sh`, results in `/mnt/cephfs/xingchao/experiments/jev/dedup_models_verify/`):
  same revision line, 0 differing lines across all 10–16 files per model. The duplicates were then
  removed, reclaiming about 67 GB on a filesystem at 92% use.
- `/mnt/cephfs/xingchao/omni/models/jev` is now a symlink to `../../models/jev`, so paths written into
  the superseded `rl_ascend_verl_20261029` configs still resolve.
- Models belonging to other projects (embedding, ASR, `qwen3-omni-30b-*`, `serving-views`, about
  200 GB under `omni/models/`) were **not** touched: they may be serving live traffic, and the
  instruction's scope for them is unconfirmed.

**The verification got the wrong answer first, and the script was the cause.** Its first version hashed
every file in each model directory and aggregated, and reported all 9 models DIFFERENT — including the
one just verified against the Hugging Face API file by file. Each model directory carries a
`.complete` provenance file holding the revision hash *and the local download timestamp*, so two
correct copies of one revision necessarily differ in it. The fix was to exclude the provenance file
from the content hash, compare the revision line separately, and diff per file so the verdict names
the differing file. A second check was then applied to the corrected result, because it came back
perfect: the elapsed time implied about 1.07 GB/s of hashing, the per-model times scaled with model
size, and a known-good hash was present in the list — consistent with real work rather than an
empty comparison.
