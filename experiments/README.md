# Pre-experiment task set (English data, smallest-model ladder first)

Status: **preparation only**. Nothing here is a training recipe; the survey (chapters 1–9) stays analysis-only.
This directory holds the task definitions and the builders that derive evaluation / training files
from the locally mirrored public datasets (`/mnt/cephfs/xingchao/datasets/jev`). Outputs go to
`/mnt/cephfs/xingchao/experiments/jev/<task>/` and are not committed; only manifests are.

Decisions this set implements (2026-10-28, survey §2.2.1 "取定的结构"):

- Order: task definition → input → one branch per candidate rule / state.
- Candidate sets declare `exclusive` (one state, isolated branches + joint softmax) or `stackable` (independent Noul per candidate).
- Levels (states) are expert-defined: name, definition, and type (`boolean | nominal | ordinal`) are all required.
- Model output: a level distribution per question. Harness: cumulative-mass thresholds, residual → C (unknown / deny); margin + explicit `abstain` for exclusive sets.
- Smallest pair first: `Qwen3-0.6B` (attention-only) vs `Qwen3.5-0.8B` (hybrid) — this pair *is* the defect-11 control. There is no 0.3B Qwen locally.
- Server: `175` (k8s-node1) has cephfs mounted; its 8 NPUs are currently fully occupied by a vLLM deployment (see `SERVER-175.md`).

## Tasks

| id | question it answers (survey anchor) | derived from | labels needed | status |
| --- | --- | --- | --- | --- |
| T1 level-name invariance | does the readout change when the expert's level names change (1–5 / a–e / words / random strings)? (defect 17, §3.1.2.2) | typed-decisions `score`+`choice` questions; akhilaaa3 medium; Open-Jev synthetic `score` | none (invariance) | builder done |
| T2 definition-swap / level-reorder discrimination | does the distribution move when adjacent level definitions are swapped or levels reordered? (defect 17 degenerate optimum) | same as T1 | none (discrimination; expected direction known) | builder done |
| T3 question-set add/remove invariance | does a readout change when unrelated questions are added / removed / reordered in the prefix? (P1″ new item, Bongard isolation test) | typed-decisions (5 questions per input) | none | builder done |
| T4 hybrid vs attention-only control | can a candidate branch recover non-salient aspects of the input through 48 recurrent layers? (defect 11) | typed-decisions; akhilaaa3; kev `binding-v1` | existing gold | spec only; needs NPU/GPU |
| T5 accuracy floor, untuned vs decision-tuned | does decision tuning keep what the base already reads? (P2″; §6.1.5) | typed-decisions, akhilaaa3, Open-Jev v1.1 `ood`, kev `binding-v1` | existing gold | spec only; needs NPU/GPU |
| T6 margin distribution and C-branch inflation | how much mass sits near τ; how much the middle level is over-populated (ordinal compression) | Open-Jev synthetic `score` (code labels), typed-decisions `score` | existing gold | spec only |
| T7 exclusive vs stackable scoring | isolated+softmax vs independent Noul: IIA on ranking / probability, and accuracy cost | Open-Jev synthetic `choice`+`noul` pairs (same group, same state) | existing gold | spec only |

T1–T3 need no new labels and can run on CPU for the 0.6B/0.8B pair (slow but feasible); T4–T7 need an accelerator.

## Files

- `build_tasks.py` — builds T1–T3 jsonl files + `manifest.json` from the local mirrors (run with `python3 -I`, needs `pyarrow`).
- `SERVER-175.md` — what was found on the server and what is still needed there.
- Record format (all tasks): `{"task": ..., "variant": ..., "group_id": ..., "input": str, "task_definition": str, "question": str, "levels": [{"id","name","definition"}], "level_type": "ordinal|nominal|boolean", "candidate_set": "exclusive|stackable", "gold": optional}`.

## 与研究提案的对应

本目录是 [`proposal/00-research-proposal.md`](../proposal/00-research-proposal.md) 的实现层。T1–T7 全部落在提案的 **R0（口径与基线，无权重更新）**，它们的作用是判定 **G1 关口（指标可测）**：

| 任务 | 提案中的预先登记项 | 它判定什么 |
| --- | --- | --- |
| T1 档位名不变性 | R0-3 | 档位名从 1–5 换成 a–e / 业务词 / 随机串时读出是否移动（缺陷 1、17） |
| T2 定义互换 / 档位重排 | R0-3 的**判别项** | 名字不变性的退化解是"完全忽略名字"，本项封住它 |
| T3 问题集加减重排 | P1″ 的新增不变性项 | 取定顺序下加入新问题会改变已有读出（缺陷 11 的接口侧后果） |
| T4 混合 vs 纯注意力 | R0-4 | 缺陷 11，报告里零命中且被测量阻塞的两行之一 |
| T5 正确率地板 | R0-6 与 P2″ | 未调优读出是否达到调优后的 76%–97%；退化模型的封堵线 |
| T6 边际分布与 C 分支 | R2-3、R4-4 | 累积质量取阈相对 argmax / 期望的优势；序数压缩对 C 分支的膨胀 |
| T7 互斥 vs 可叠加 | R2-4 | 菜单相对性（四根承重柱之一）在我们设置下的复现 |

R0 还有三项本目录尚未覆盖的任务，均属评测线：四分母并排的一致率口径（`E-0.2`）、同骨干标签对数概率基线（`E-0.3`）、退化基线与四柱复现（`E-0.4`/`E-0.5`）。
