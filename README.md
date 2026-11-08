# NGA — Jev-class decision-model research

[GitHub](https://github.com/chaosxingxc-orion/nga) · [GitCode](https://gitcode.com/xingchao_ml/nga) · [Synchronization](https://github.com/chaosxingxc-orion/nga/actions/workflows/sync-gitcode.yml)

NGA means **Next Generation Agent**. This repository now focuses on its model-research program: define decision tasks from enterprise business goals, build traceable data, reproduce and improve Jev-class models, and evaluate consistency, correctness and business configurability.

**Framework architecture, S1 + S2 cooperation, the enterprise workbench and agent-festival reference components have moved to [Agent Hub Alpha](https://github.com/chaosxingxc-orion/agent-hub-alpha)** and its [GitCode counterpart](https://gitcode.com/xingchao_ml/agent-hub-alpha). See the [migration record](docs/REPOSITORY-SPLIT.md).

## Research objective

Generative agentic models may reconsider the same business basis and produce different consequential decisions. NGA studies consistency under equivalent inputs, discrimination when material facts change, rule/definition following and configurable business semantics. Consistency alone does not establish correctness; repeated answers do not prove valid business outcomes.

Jev, KEV, BEV and related reproduction baselines, continued training and evaluation remain here, together with the infrastructure needed to reproduce them. Published research informs the analysis; it does not replace business goals or evidence requirements.

## Start here

| Purpose | Entry |
| --- | --- |
| Current conclusions | [Current conclusions](wiki/CURRENT-CONCLUSIONS.md), [GitHub Wiki](https://github.com/chaosxingxc-orion/nga/wiki/Current-Conclusions) |
| Collaborator startup | [Experiment onboarding](docs/EXPERIMENT-ONBOARDING.md) |
| Research analysis | [Survey](survey/README.md), [PDF](survey/nga-survey.pdf) |
| Tasks and gates | [Research proposal](proposal/00-research-proposal.md) |
| Protocols and code | [Experiments](experiments/README.md), [R3 snapshots](experiments/r3_sft/README.md) |
| Execution infrastructure | [Configuration](configs/experiments/README.md), [engineering base](docker/engineering-base/README.md), [tools](tools/README.md) |
| Framework architecture | [Agent Hub Alpha](https://github.com/chaosxingxc-orion/agent-hub-alpha) |

Current conclusions and registered protocols govern experiment status. Historical result pages do not automatically establish that G1/G2/G3 or a production capability has passed.

## Working boundaries

- Register metrics, splits, thresholds and decision criteria before runs; record amendments explicitly.
- Pair invariance objectives with discrimination tests and degenerate baselines. Accuracy is not the consistency metric.
- Keep the survey analytical; plans in proposal/, protocols/code in experiments/, current evidence in wiki/.
- Weights, generated data, checkpoints and full outputs remain on the existing Linux/Ascend/shared-storage environment, outside Git. No new local training environment is required.
- Framework changes belong in Agent Hub Alpha; model experiments and their execution dependencies belong here. Link versioned interfaces and evidence rather than copying entire repositories back together.

[CLAUDE.md](CLAUDE.md), experiment protocols and [wiki rules](wiki/README.md) retain their research-specific authority. This split changes ownership and navigation, not experimental preregistrations or live server execution.
