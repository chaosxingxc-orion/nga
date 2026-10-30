# 共同参考评测：JEVal / typed-decisions 接口预检与待执行协议

2026-10-30。状态：只读数据与原生接口核查完成；尚未执行这两个共同测试集的模型推理。本文件是下一次预注册的具体输入，不是已冻结运行或已验收结果。机器可读证据：[inventory](COMMON-REFERENCE-EVALUATION-INVENTORY-2026-10-30.json)。现有直接文献对应推理继续，正式训练仍等待 D1 指标汇报及方案讨论。

## 1. 实际数据和两层 split

175 上两套 `/datasets/jev/` 与 `/omni/datasets/jev/` 均已搜索，以下完整文件在 `omni`，没有下载或重抽样。

| 数据 | 实际文件（相对 `/mnt/cephfs/xingchao/omni/datasets/jev/`） | 行 / 问题 | SHA256 |
| --- | --- | ---: | --- |
| JEVal | `carlosxiang__JEVal/data/test.parquet` | 11,257 / 11,257 | `88f090a510e511d1236fdf5ddb428a8b965663ff0cc1061f950b88f0c99d2e82` |
| typed-decisions | `LocalLLaMA__typed-decisions/all/test-00000-of-00001.parquet` | 400 / 2,000 | `4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c` |

JEVal：9,582 choice、1,356 noul、319 score，58 个 source，ID 全唯一。该集合自身为 test，但 `source_item_id` 标示原始 **8,257 test / 2,000 train / 1,000 dev**。Parquet 元数据亦对应 43 个 test-source、10 个 train-source、5 个 dev-source。不能将全集称为“所有上游均未见测试集”，也不能删去 train/dev 行后仍引用原 Table 1 的 10,938 分类分母。若另报上游 test-only，须预先固定那 8,257 行并单列，不能替换官方全集。

typed-decisions：四个 workflow 各 100 states；600 choice、600 noul、800 score；所有行自身 split 为 test，ID 全唯一。每个 state 五个问题，候选数为 2–5。gold 是分布；547 个问题的序列化 gold 概率和并非精确 1，范围约 `[0.999999,1.000001]`。原 scorer 不归一化 gold，原生复现必须保留这个细节，不能无记录地“修正”标签。

## 2. 原生接口能承接哪些单元

| 模型 | typed-decisions | JEVal | 不得静默改变的边界 |
| --- | --- | --- | --- |
| Kev 0.8B / 4B / 9B | 类型与候选数兼容；需完整 token 预检 | API 支持至 255 候选，覆盖实际最大值；需长文本及 packed context 预检 | 原生 pointer readout、联合问题结构、顺序及 checkpoint 温度；不改为生成标签 |
| Open-Jev 2B / 9B | 类型兼容；原生 API 将各问题编译成隔离候选记录 | API choice 支持至 255，score 支持 2–10，当前数据兼容；长输入仍未知 | 每候选 scalar head，4096-token 路径和拒绝截断；score 候选顺序是回映射，不给模型增加邻级信息 |
| 初始 Nimble 9B，revision `594dfdcfb6f94e3d0c0db7535180d3c71689169a` | 最多 5 候选，v1 schema 可承接；需完整 prompt 预检 | **原 v1 接口不能全量承接：2,047 行 choice 超过 26 候选** | 原 contract 明确选择 `parallel_schema`，最多 26；不能换 v2/v3 或 experimental 255-code prompt 后仍称初始模型原生复现 |

JEVal 超过 26 候选的 2,047 行覆盖 11 个 source：aida-testc、clinc150、go-emotions、helmet、lex-glue-ledgar、longbench-retrieval-en、longbench-retrieval-en-e、longbench-retrieval-zh、longbench-trec、longbench-trec-e、nlu-eval-68。具体计数见 inventory。初始 Nimble 在其余 **9,210 行 / 8,891 分类问题**上可作另名的结构兼容子表；全量协议应把 2,047 行明确记为 unsupported，而非漏记、零概率或任意剪掉候选。尚未完成 token 检查，9,210 也不是已确认可推理分母。

源码依据（175 本地路径）：

- `repos/jev/jaredpalmer__kev/kev/api.py:14,94–117`：255 上限；choice 保留键顺序，noul 映射 false/true，score 按原数组索引。
- `omni/repos/jev/Zefan-Cai__Open-Jev/jev/api.py:24–85`：三类 compile、候选上限与独立 candidate prompt；`jev/model.py:239–240`：超长报错，不静默截断。
- `omni/repos/jev/bespokelabsai__nimble/nimble/training/candidate_schema.py:53–63`：v1 返回原 `parallel_schema.prepare_prompts`；`nimble/scoring/parallel_schema.py:26–55`：enum 1–26、布尔两项及 description 类型约束。仓库确实另有 serving 255 扩展，但不是本次初始 adapter contract。

两个 model mirror 均已搜索。六个拟用 checkpoint、base revision、adapter/head SHA256、现有运行 config SHA256 均记录在 inventory，避免用目录名替代版本。Kev 使用原生发布温度并另报 raw T=1；Open-Jev 温度固定 2B `1.518796342858676` / 9B `1.8969118766347646`；初始 Nimble T=1，不能借后来温度来优化共同 test。

## 3. 输入与 typed readout 映射

只传 state 和 questions；ID、source、label/gold、factors、label_agreement 不进入模型。保留 JSON 对象插入顺序，尤其 choice 顺序；canonical hash 之外另保存 ordered candidate keys。每题身份为 `(dataset_hash, original_row_index, original_id, question_id)`。

**JEVal**：按照数据卡 `README.md:77–83`，state 保留原字符串，questions/label 各自 JSON 解码；不要因为 state 看似 JSON 而再次解析后改变原生呈现。label 仅供评分。**typed-decisions**：按照原 scorer `score_with_jobs.py:65–69` 解码 state 为 JSON 对象，questions 为对象；四个 workflow 的每行五问题作为一个原请求。

- choice → nominal：候选 key 为 level 名，criteria value 为定义；空字符串、null 不造新定义，不把 key 归一化或重排。
- noul → boolean：固定 false/true 两候选；1,356 JEVal noul 的 label 是 JSON 整数，严格核对 0/1 后转评分布尔，不靠 truthiness。typed-decisions 有 200、JEVal 有 236 个 noul 无 criteria，保留 absence，由各原生接口使用默认 no/yes 或 false/true。
- score → ordinal：保存原 level 数组，回映射为 `"0"…"K-1"`；保留全分布与 expected score。不能用 expected score 四舍五入冒充分布 argmax。
- Nimble 需要 enum/boolean schema：instructions 作为 description；choice key/定义分别进入 choices/choice_descriptions，null 定义不传为字符串 `"None"`；score 使用索引字符串 choices 及原数组定义。全部 instructions 实测为非空字符串。将整个 typed-decisions schema 传给原 prompt builder，使各 field 的原生 prompt 可看到同一 schema；不能任意改成单题 schema 而宣称同接口。
- 原生 formatter 可能只返回 `noul` 标量而不返回 probabilities（Kev `api.py:152–153`、Open-Jev `api.py:112–115`）。共同评测 adapter 必须从原始已保存分布保留 false/true 两概率；若评估原 wire response，则另列 transport 口径，不能把缺失 probabilities 当真实 uniform 模型预测。

## 4. 指标与无效回答：保留原方法，再独立列严谨口径

### typed-decisions 原生计算

冻结 `bench/score_with_jobs.py` SHA256 `6854ef67b8cff64ebc71e5b47d0f44e78f92124fc0d62f539095cab5625844f8`。

`26–41`：gold 概率键序决定向量序；noul 的 yes/no 转 true/false；缺少预测 key 补 0；预测总质量正则归一化，否则替换 uniform。argmax 并列取第一个；gold 不归一化。`KL=Σ q log(q/max(p,1e-9))`，`Brier=Σ(p−q)²`。`74–79`：缺失整题也传空分布，因此变成 uniform，不能说原生缺失题必定计错。`84–104`：10 个等宽 bin，`min(int(conf*10),9)`；conf 为 max probability，accuracy / KL / Brier / ECE 均问题等权，2,000 分母。

同时报告严格审计面：expected 2,000、returned、valid、invalid、unsupported、overlength、failed；accuracy 的无效题计错、分母固定 2,000，概率指标只在完整有限非负有效分布上计算并标 n_valid。这与原生 uniform fallback 分开命名，不能替代原文数字。非有限、负概率及额外键不能悄悄变成有效预测。使用原始未舍入概率作为原生 readout 新比较，并另保存 wire-rounded 映射；不能把其差异称为硬件数值误差。

### JEVal

数据卡 `README.md:93` 确认：classification 10,938，accuracy 无效回答计错，ECE/raw Brier 只用有效回答；319 score 单列。原 ECE bin 数、边界与 score 指标的完整定义尚未由本地评分源码证实。数据卡指向 `amazingljy1206/InnerJev`，两个 repo mirror 中未找到该仓库；当前本地只有数据打包 `scripts/merge_eval.py`，它不是 scorer。

因此可预注册本项目独立的 question-micro one-hot summed Brier、ECE10 和 score expected-value MAE/argmax accuracy，但必须标为**新增统一口径**，不能直接贴上“JEVal 原文 ECE/score 完全复现”。启动前优先获取/核查对应固定 revision 的原 scorer或论文公式；如果仍不可得，accuracy、有效分母及统一口径先交付，原文公式复现格保持未确认。不得从 test 结果挑 ECE bin、温度或 score rounding。

## 5. 下一项可执行工程任务及验收

1. 优先实现 typed-decisions 六模型 adapter；保留原生 schema/request shape，输出原始 logits/probabilities、typed 映射和 exact row/question receipt。先对合成五问题 state 做编译验证，再对全 400 states 做 token-only 长度预检；不读结果调 prompt。JEVal 并行做完整 token/候选资格清单和原 scorer 核对，不为了短任务而缩小全集。
2. 合成正例：含 boolean、4-choice、4-level score 的五问题结构，空/null 定义，中文及嵌套 state，候选同分并列。反例：调换两候选/其定义须改变对应映射；只改 gold 不得改变 prompt；缺题/额外题/错误索引/非有限概率须被拒绝；Nimble 27 候选应原生报 unsupported，26 候选正例通过。它们对应 defect 12/16；忽略输入的常数输出是退化最优，接口通过不证明有效决策或一致性。
3. 固定执行清单后登记 wiki 和独立协议：数据 SHA、模型/原生代码全依赖、精度、长度和超长策略、温度、所有分母/公式、seed（若无随机推理明确不适用）、吞吐探测及验收边界。与现有大任务隔离，175 固定 retained Docker、日志/心跳/terminal、逐项恢复、资源锁及容器实映射；超过一分钟任务 detached。
4. 真实执行后由不导入 native metric 的独立 scorer 从逐项分布复算，检查完整身份覆盖；0/1、小样本、全部格相同触发审查。上游表、原生 scorer、本项目统一方法三者分列。不将 aggregate accuracy 充当 decision-level consistency；一致性需另行预注册成对 protocol，并配辨别反例。

目前尚缺的是 adapter 实现及合成测试、各接口完整长度统计、JEVal 原评分源码、实际运行与独立验收。没有真实业务部署依赖，也没有新的训练或训练收益声明。本文件不擅自批准完整所有本地模型 × 所有数据集的交叉扩展。
