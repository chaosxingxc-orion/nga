# NGA — Next Generation Agent

**NGA explores the integrated design and implementation of System 1 + System 2 agent frameworks, grounded in Jev-class engineering reproduction and decision models redesigned around business needs.**

The preceding generation of agent frameworks centers on an **agentic model**: the model plans, executes actions, reflects on observations, and replans through an **agent loop**. As Jev-class decision models develop, NGA asks how inexpensive, typed judgments can work with generative reasoning to change the way an agent is organized.

The project connects three areas of work:

1. **Jev engineering reproduction** establishes what the reference approach does, how it is built, and which results we can reproduce.
2. **Business-driven model redesign** develops the decision capabilities and interfaces required by our intended workloads.
3. **System 1 + System 2 framework design** brings those capabilities together with reasoning, planning, execution, and control.

The integrated framework is the project vision. The model experiments provide its empirical foundation. **The concrete architecture remains open.**

## How the work fits together

```mermaid
flowchart LR
    A["Jev engineering reproduction"] --> B["Business-driven model redesign"]
    B --> C["System 1 + System 2 framework design"]
    C -->|"Capability and interface requirements"| B
    B -->|"Questions for controlled comparison"| A
```

These are connected workstreams. Reproduction provides a baseline for evaluating changes; business objectives determine which changes matter; framework experiments test whether model capabilities produce useful system behavior. Findings from each workstream can revise the others.

### 1. Reproduce Jev-class engineering

The first engineering objective is a reproducible path through **data preparation, training objectives, inference/readout, and evaluation**. This includes reference-recipe comparisons and the controls needed to separate genuine capability from label priors, prompt artifacts, or measurement defects.

The current model work starts with small Qwen-family decoders. The research plan uses `Qwen3-0.6B` as an attention-only control and explores the Qwen3.5 0.8B, 2B, 4B, and 9B ladder. Larger-model options remain part of the longer-term proposal.

Reproducing a training recipe, matching a benchmark, and reproducing a native typed-readout architecture are separate milestones. Every result must state which milestone it supports.

### 2. Redesign the model around business objectives

The intended use is **frequent semantic judgment inside business processes**. Business authors should be able to express criteria in questions, definitions, examples, and declared output states. The model should interpret those criteria and return typed observations that programs can use.

For example, two inputs can count as equivalent under one business question and require different decisions under another. The desired behavior is to preserve decisions when the business meaning is unchanged and change them when the supplied rule requires a distinction.

The model-side foundation has three intended deliverables:

| Deliverable | Purpose |
| --- | --- |
| **Business-authoring standard** | Specify questions, level names and definitions, types, criteria, and examples. |
| **Decision model** | Read the supplied specification and produce a distribution over declared levels, or a probability for each independently applicable candidate. |
| **Decision harness** | Apply registered thresholds, margins, abstention, and unknown handling to turn observations into program decisions. |

The current proposal investigates `boolean`, `nominal`, and `ordinal` level types, with `exclusive` or `stackable` candidate sets. Its proposed input order is **task definition → input → candidate branches**. These are model-interface choices to evaluate within the research program.

The business case depends on useful decisions at a low enough cost to make repeated judgment practical. Evaluation therefore includes **accuracy floors, definition following, consistency within business equivalence classes, discrimination when rules change, and unknown handling**. Calibration and reliable escalation must be measured on the intended workload.

The [survey's business-goal analysis](survey/05-system-business-goal-and-positions.md) and [interface definition](survey/02-propositions-and-core-logic.md) explain the rationale and its limits.

### 3. Design the combined System 1 + System 2 framework

**System 1** contributes fast, typed judgments. **System 2** contributes generative reasoning, planning, and adaptation. NGA investigates how their responsibilities, shared context, execution mechanisms, and feedback should be designed together.

Candidate uses of System 1 include routing, process monitoring, evidence and memory selection, evaluation of intermediate states, and readout of System 2's reasoning. Each placement has different capability requirements and failure modes.

Framework success must be measured end to end: **task success, cost per successful outcome, latency, recovery behavior, and the ability to trace consequential decisions**. A cheaper isolated judgment does not establish a better agent.

## Architecture: questions under exploration

The supplied enterprise-agent architecture references contribute questions about capability contracts, execution graphs, permission boundaries, context sharing, and accountability. They inform NGA's design space; their implementation claims, host platforms, and proposed mechanisms are not NGA implementation status.

| Design area | Questions to resolve |
| --- | --- |
| **Control and orchestration** | Who owns the loop and scheduling? Which decisions belong to S1, S2, deterministic code, or a person? How are handoffs and failures handled? |
| **Capability contracts** | How should a capability declare its inputs, outputs, required authority, effects, and resource bounds? |
| **Execution structure** | When should execution use a loop, graph, bounded workflow, or a combination? How should runtime planning interact with declared constraints? |
| **Context and intermediate results** | What evidence does each component receive? How should results be isolated, shared, verified, and reused? |
| **Authorization and enforcement** | How should delegated authority and budgets be constrained, and where should those constraints be enforced? |
| **Accountability and feedback** | How are proposals, verification, adoption, execution, and outcomes linked? Which feedback can validly improve the model or controller? |

These questions leave the runtime, implementation language, control topology, authorization mechanisms, and integration platform open. Existing proposal defaults are hypotheses or recommendations to test, rather than settled NGA architecture.

## What is in the repository today

This is an active research and engineering repository. It currently contains analysis, plans, experiment code, and records; the integrated NGA framework remains to be implemented and evaluated.

| Area | Contents and entry point |
| --- | --- |
| **Survey** | Nine analytical chapters covering Jev-class models, semantics, consistency, business value, fast/slow cooperation, and limitations. Start with [`survey/README.md`](survey/README.md); a [PDF](survey/nga-survey.pdf) is also available. |
| **Research plan** | R0–R8 hypotheses, work packages, dependencies, and decision gates. See the [proposal](proposal/00-research-proposal.md) and [four-direction work plan](proposal/01-work-plan-four-directions.md). |
| **Tasks and protocols** | Data builders, manifests, frozen protocols and amendments, and result documents in [`experiments/`](experiments/README.md). |
| **Baseline code** | Prompt rendering, candidate scoring, splits, threshold fitting, paired metrics, and reporting in [`experiments/r0_baseline/`](experiments/r0_baseline/). |
| **SFT code snapshots** | Data preparation, training, evaluation, and launchers in [`experiments/r3_sft/`](experiments/r3_sft/README.md). Its `r1_code` directory means SFT round 1, not proposal round R1. |
| **Experiment records** | Purpose, hypothesis, setup, results, and verdict for each recorded experiment in [`wiki/`](wiki/README.md). |
| **Operational tools** | Monitoring digests, anomaly flags, and model-copy verification in [`tools/`](tools/README.md). |

### Recorded progress and current limits

The following describes the committed experiment records, rather than live server state:

- **R0:** an untuned readout baseline has been run and [reported](experiments/R0-BASELINE-RESULTS.md). A scorer-padding defect has a pending erratum; those published numbers cannot serve as the R0 side of new comparisons until resolved. This run uses **candidate-label token log-probabilities**, and does not demonstrate a native typed-readout head or a typed-readout advantage.
- **Control checkpoint:** [F1](wiki/F1-fetch-qwen3-0.6b.md) records the Qwen3-0.6B checkpoint as fetched and verified. That record does not contain the hybrid-versus-attention experiment result.
- **First SFT round:** the [R3 protocol](experiments/R3-SFT-PREREG.md) is frozen with amendments. [K0](wiki/K0-untuned-readout.md) and [W1](wiki/W1-wave1-first-weight-updates.md) remain marked **planned**. Scorer-admissibility measurements and the recorded efficiency prerequisites must be completed before the relevant runs of record.
- **Research gates:** G1 (consistency measurement), G2 (definition following), and G3 (business-author configurability) are evidence requirements in the proposal. The present records do not establish that they have passed. R3's permitted pre-G1 accuracy SFT cannot be used to claim a consistency result or a gate pass outside its registered scope.

## Working principles

- Keep repository artifacts, model prompts, comments, and commit messages in **English**.
- Treat proposed capabilities and architecture choices as falsifiable hypotheses. State the shortcut or degenerate solution an experiment must exclude.
- Pair every invariance objective with a discrimination test, and report accuracy floors and degenerate baselines alongside consistency.
- Register metrics, splits, thresholds, and decision lines before running. Make protocol changes through explicit amendments.
- Write experiment purpose, hypothesis, and setup before launch; add results and verdicts from the run's own artifacts afterward.
- Keep the survey analytical, engineering plans in `proposal/`, and experiment protocols and evidence in `experiments/` and `wiki/`.

Experiments use the existing Linux / Ascend NPU environment and shared storage. Model weights, datasets, generated task files, checkpoints, and full run outputs are held outside Git. The R3 code in this repository is a snapshot of working copies on shared storage; reconcile versions and record provenance before editing or launching. A local training environment is not required to read or contribute to the project documentation.

For detailed research and run conventions, see [`CLAUDE.md`](CLAUDE.md), the [experiment guide](experiments/README.md), and the [wiki rules](wiki/README.md). The pre-registrations govern experimental claims; this README introduces the project and does not amend them.
