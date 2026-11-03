# 15 · T1 真 LLM 读数（2026-11-03 夜，单次运行存档）

> 运行：用户授权启动（「跑T1」）；端点 gptplus5（anthropic-messages 协议，/v1/messages 探针 2.8s 预确认）；模型 glm-5.3-flash；thinking 恒开（max_tokens 4096）；7 调用全单发命中（无重试），时延 3.5-7.7s/调用，总 34.6s。
> 证据纪律（XM2/ReAnchor）：单次运行=当日锚，跨日禁引；非统计主张（一致性对 n=2）；引用作装配依据前须复测。

## 结果：7/7 判定全对

| 用例 | 期望 | 实得 | 硬门 | 模型理由（截录） |
|---|---|---|---|---|
| C1 干净授信 | grant-50000 | grant-50000 | ✓过 | 35>30 且六月无逾期、全程无>3月逾期→Precedence 1 |
| **C2 窗口外否决（复审者反例）** | deny | deny | ✓过 | 两年前 4 月逾期>3 月触发 Precedence 0「at any time regardless of assets」 |
| C3 缺证 | on_missing_evidence | on_missing_evidence | ✓过 | 报告不可取→请求补证；无否决触发故不自动拒 |
| C4 C2 改述 | deny | deny | 对内 | 同事实换措辞→同判 |
| C5 C1 改述 | grant-50000 | grant-50000 | 对内 | 同 |
| C6 带间开放（无门首测） | on_undefined_rule | on_undefined_rule | 报告 | 12 严格介于 1/30→未决区「no grant can be defaulted, the issue must be recorded」 |
| C7 窗口内否决锚 | deny | deny | ✓过 | 3.5 月逾期触发 Precedence 0 |

一致性对：C1≡C5=grant-50000；C2≡C4=deny。harness 健康：全过（无传输/解析失败）。

## 解读（诚实口径）

1. **载重判别用例（C2）通过**：模型正确应用了无窗口限定的历史否决——判别能力（四能力表第 2 行）在本端点+本模型上有了第一个绿数据点。
2. **一致性（第 1 行）**：两组改述对同判——但 n=2、单次；是方向证据非稳定性主张。
3. **C6 无门项意外通过**：模型守住了「带间不默认授信」的开放边界纪律——下一轮预注册的升门候选（单次测量不构成升门依据，升门=新预注册）。
4. **对协商的意义**：D1（模型就绪独立设门）的 S1 席位有了首份绿读数（flash 档）；不改变「双打过 M02 才宣称生产用途」的原有主张——那是 SDK 级主张，这是单点判位读数。
5. T1 的 harness 自身集成测试同步完成（传输/解析全通，anthropic-messages 协议确认）。
