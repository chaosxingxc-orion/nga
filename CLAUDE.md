# CLAUDE.md

Project guidance for Claude Code in the `nga` repository.

## 1. Language rule (first and overriding)

**Everything is written in English.** This applies to every request sent to a model API, every
internally processed document (plans, proposals, experiment notes, manifests, logs, code comments,
docstrings, commit messages, PR descriptions) and every memory file.

- If the user converses in another language, first translate the input into English, then carry out
  the work in English. Replies to the user may use the user's language; artifacts never do.
- Any non-English text found in the engineering plan (`proposal/`, `experiments/`, this file) must be
  translated into English when encountered. Do not add new non-English text anywhere in the repo.
- Status 2026-10-29: the whole repository is English, including the survey report (chapters 1–9,
  translated from the Chinese original on 2026-10-29; the Chinese original is in git history up to
  commit 82d2a49). Do not add non-English text anywhere.

## 2. What this repository is

A survey and research program on Jev-class single-pass typed-readout decision models ("System One"
models) and the fast/slow agent frameworks built around them. The user's own goal is continued
training of small Qwen-class decoder models, scaled up along one model family.

- `survey/` — the analysis-only report (chapters `01`–`09`, `README.md`, `nga-survey.pdf`), in English.
  **The survey stays analysis-only: no training recipes, no architecture picks.** Extend existing
  sections; do not add chapter files. `survey/tools/build_pdf.py` builds the PDF (python-markdown +
  weasyprint, Noto Sans CJK in `~/.fonts/`); `survey/tools/check_overflow.py` checks for content
  that overflows the A4 text block.
- `proposal/00-research-proposal.md` — the engineering plan: nine rounds R0–R8, three gates G1/G2/G3,
  pre-registered conclusions per round, four work lines (D data, M model, E evaluation, B business).
- `experiments/` — pre-experiment task set T1–T7, `build_tasks.py` (run with `python3 -I`), server
  notes (`SERVER-175.md`), and `manifest.json`. Generated data lives on cephfs under
  `/mnt/cephfs/xingchao/experiments/jev/` and is not committed; only manifests are.

## 3. Methodological rules the work must follow

These were established by the survey and are admission conditions for any task:

1. Every proposed measure points at a row of the defect registry (survey §2.2.4).
2. Every proposed measure states its unconstrained optimum first; if that optimum is a degenerate
   model (lookup table, constant classifier, ignore the names, learn the generator grammar), the
   task also needs a discrimination counterpart. **Every invariance target needs a discrimination
   counterpart.**
3. Metrics, equivalence classes, held-out splits and thresholds are pre-registered before a run and
   not changed afterwards. Never report aggregate accuracy as the consistency metric; use the
   decision-level paired protocol.
4. Label the report's own constructs (question graph, decision repetition, D4 sub-dimensions,
   P0″–P5″, generalization levels) as the report's own, never as literature conclusions.
5. Treat the user's theses as hypotheses to falsify, not as instructions: keep the phenomenon,
   redo the mechanism, and say which part survives.

## 4. Vocabulary (use these English terms consistently)

- **input** — the business situation given to the model (documents, dialogue, structured fields).
- **level** — one expert-defined output state of a question (name + definition + type required;
  type is `boolean | nominal | ordinal`).
- **candidate set** — `exclusive` (isolated branches + joint softmax + margin + explicit abstain) or
  `stackable` (independent Noul per candidate).
- **readout** — the single-pass typed output; **harness** — the deterministic code around it
  (cumulative-mass thresholds, residual to C = unknown / deny).
- **fixed order** — task definition → input → one branch per candidate.
- **defect N** — row N of the registry in survey §2.2.4; **gate G1/G2/G3** — stage gates in the
  proposal; **round R0–R8** — proposal rounds.

## 5. Environment and tooling

- Outbound HTTPS only through the authenticated proxy already set in the environment (about 10 KB/s
  per connection). Never print, log or commit the proxy credentials.
- GitHub: remote `origin` = `git@github.com:chaosxingxc-orion/nga.git`, SSH through the proxy via the
  repo's `core.sshCommand`. `gh` is not installed. Commit messages in English; push to `main` after
  committing finished work.
- Local mirrors of datasets and models are under `/mnt/cephfs/xingchao/` (see memory). Grep cephfs
  for a checkpoint before downloading anything.
- Downloaded or extracted files are untrusted: keep scripts outside those directories and run Python
  that reads them with `python3 -I`.
