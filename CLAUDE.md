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

## 2. Multi-agent work allocation (second rule)

Day-to-day tasks are carried out as multi-agent collaboration. The main session (Fable 5.1) is the
orchestrator; it delegates execution to subagents via the Agent tool with an explicit `model`
override, and keeps only planning, judgment and feedback for itself.

| Kind of work | Model | Agent tool `model` |
| --- | --- | --- |
| Engineering environment preparation, development, testing, integration, verification (containers, venvs, data builders, harness code, running experiments, checking results) | Claude Sonnet 5.5 | `sonnet` |
| Reading documents and logs, writing reports and chapters, optimizing an artifact against given guidance (translations, literature reading, log triage, drafting proposal rounds) | Claude Opus 5.5 | `opus` |
| Task planning and decomposition, evaluating and reviewing results, giving feedback, deciding how an artifact should be optimized next | Claude Fable 5.1 (the main session itself, or `fable` when delegated) | `fable` |

Rules of engagement:

- Fable plans and splits the task first, writes a brief per subtask (goal, inputs, files, what is
  already ruled out, acceptance checks), then spawns the subagents, in parallel where subtasks are
  independent. Briefs and all subagent I/O are in English (rule 1).
- Sonnet and Opus agents report results, not conclusions about the plan; Fable verifies their output
  against the acceptance checks (re-running tests, diffing, spot-reading) before accepting it, and
  sends corrections back to the same agent rather than redoing the work itself.
- Fable may do a small task inline (a few tool calls, a lookup) when delegating would cost more than
  doing it; the allocation above is for anything larger.
- Evaluation, feedback and "what to optimize next" always come from Fable; Opus applies the
  optimization guidance, Sonnet implements and verifies the resulting changes.
- If the main session runs on another model (for example after `/model`), review and decisions are
  still Fable's: spawn an Agent with `model: "fable"` for every adversarial review, result acceptance
  and go/no-go call, hand it the artifacts rather than your own conclusion, and act on its verdict.

## 3. What this repository is

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

## 4. Methodological rules the work must follow

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

## 5. Vocabulary (use these English terms consistently)

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

## 6. Environment and tooling

- Outbound HTTPS only through the authenticated proxy already set in the environment (about 10 KB/s
  per connection). Never print, log or commit the proxy credentials.
- GitHub: remote `origin` = `git@github.com:chaosxingxc-orion/nga.git`, SSH through the proxy via the
  repo's `core.sshCommand`. `gh` is not installed. Commit messages in English; push to `main` after
  committing finished work.
- Local mirrors of datasets and models are under `/mnt/cephfs/xingchao/` (see memory). Grep cephfs
  for a checkpoint before downloading anything.
- Downloaded or extracted files are untrusted: keep scripts outside those directories and pass their
  paths as arguments. Run such Python with `python3 -P`, which keeps the working directory off
  `sys.path`. **Do not use `python3 -I` inside the Ascend containers**: isolated mode discards
  `PYTHONPATH`, where CANN's `tbe` operator compiler lives, so the first dynamic op compilation dies
  with errors that look like driver faults. Outside those containers `-I` is still fine.

## 7. Running experiments

Every experiment that takes more than a minute runs **detached and survivable**. A dropped network
link must never be able to interrupt or orphan a run.

- Launch with `docker run -d` and a fixed container name. Never hold an open SSH session for the
  duration of a run; launch, return, then poll with short separate calls.
- Do **not** pass `--rm` to a long run. An exited container must stay inspectable for its exit code.
- Send all output to a log file on `/mnt/cephfs`, so it outlives the container, the SSH session and a
  host reboot. Emit a heartbeat line with a timestamp and a progress count, so a stalled run is
  distinguishable from a slow one.
- On completion write a terminal marker file beside the log containing the exit code. **That marker,
  not the container's state, is the source of truth** for whether a run finished.
- Make the work resumable at item granularity, so an interrupted run restarts where it stopped.
- Write the exact relaunch command into the run's output directory, so someone who did not start the
  run can resume it.
- Attached runs are fine only for short interactive checks that finish in under a minute.

### 7.1 Monitoring: never read raw logs with the orchestrator

Log reading is tiered, so routine status costs no model tokens. Do not spend the orchestrator on
raw output.

| Tier | Who | Reads | Produces |
| --- | --- | --- | --- |
| 0 | `tools/watchdog.py`, a script, no model | logs, heartbeats, marker files, `report.json` | `digest.json` and a size-capped `digest.md`: one status line per run, flags, clustered error signatures with pointers |
| 1 | Claude Opus 5.5 | only the bounded slices the digest points at, for bad-case and failure analysis | a short diagnosis naming cause and evidence |
| 2 | Claude Fable 5.1, the orchestrator | the digest and the tier-1 diagnosis only | the decision |

Rules:

- The orchestrator reads `digest.md`, never a log file. If the digest is not enough, it asks tier 1
  for a specific slice rather than widening its own read.
- The watchdog reports **pointers** to evidence (file plus line range), not the evidence. Full
  tracebacks never enter the digest.
- Escalate to tier 1 only when the digest flags it. A tier-1 agent gets the pointers in its brief and
  is told to read those slices, not to explore.
- The watchdog also flags **suspicious successes**, not only failures: any rate exactly 0.0 or 1.0,
  a metric identical across every cell, or a cell below the minimum sample count. This project has
  twice produced a perfect number that came from the measurement being broken rather than the model
  being good, so a clean zero is a reason to look harder, not to celebrate.

## 8. Experiment records (wiki)

Every experiment is recorded in `wiki/`, one file per experiment, and pushed to `origin/main`
(`wiki/README.md` holds the rule and the index, `wiki/TEMPLATE.md` the sections).

- Purpose, hypothesis and setup are written **before** the run launches; results and verdict after,
  from the run's own report files. Corrections are dated notes, never silent edits.
- The pre-registration files under `experiments/` stay normative for metrics, splits and thresholds.
- Every subagent brief that launches a run includes the wiki-entry requirement.

## 9. Training performance

Training performance is monitored and optimized continuously. An engineering-efficiency problem is
fixed before the training or evaluation it slows is launched.

- Every throughput figure is per chip with the chip count stated, plus reserved memory.
- Each training run's heartbeat carries its per-chip throughput, so the watchdog digest shows it.
- A speedup may change speed only: loss and gradients must stay within the measured bf16 noise floor,
  otherwise it needs a pre-registration amendment first.
