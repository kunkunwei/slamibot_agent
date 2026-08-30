---
name: novel-workbench
description: 用于中文长篇网文工作台的规划、续写、写章、修订、连续性检查、篇章收束与跨会话恢复；仅在操作 Novel Workbench 的合同、草稿、Delta 和状态流程时使用。
---

# Novel Workbench

以工作区文件为跨会话记忆，按需装载上下文，并把每章视为可校验的事务。Luna 指 `gpt-5.6-luna`，Sol 指 `gpt-5.6-sol`；本地脚本不得调用模型。

## 启动与恢复

1. 先检查 `tools/novel.py`。
2. 若尚未实现，只读 `START_HERE.md`、已批准规格 `docs/superpowers/specs/2026-08-22-novel-workbench-design.md` 和实施计划 `docs/superpowers/plans/2026-08-22-novel-workbench-v0.1.md`，继续获准任务；不得假设 `novel/` 已存在。
3. 若已实现，先运行 `python tools/novel.py init`，再依次读 `START_HERE.md`、`novel/config.json`、`novel/handoffs/current.md`、当前篇章计划。
4. 恢复后只读当前任务涉及的实体、状态、摘要和必要原文。

## 真相与上下文边界

权威顺序固定为：用户确认 > 已发布正文 > Canon > 已确认 Delta/State > 大纲 > 摘要 > 推断。低层内容冲突时报告，不得覆盖高层事实。

不得无差别扫描全书。先确定章节、人物、地点、物品或伏笔，再按 HOT/WARM/COLD 路由读取。失败稿、废案、草稿和 candidate Delta 都不是正式事实。

## 模式

| 模式 | 使用时机 | 路由 |
|---|---|---|
| fast | 低风险普通章、明确过渡 | Luna 规划 → Luna 写作/定向修订 → 本地检查；Sol 0 次 |
| balanced | 默认模式、存在有限不确定性 | Luna 合同与写作 → 本地检查 → 仅命中升级条件时 Sol 审核 |
| premium | 开篇、高潮、卷末、结局、重大反转或复杂情感节点 | Sol 战略 → Luna 整理 → 选定模型写作 → Luna 预检 → Sol 终审 |

普通章最多调用 Luna 场景/上下文 1 次，加 Luna 写作或修订 1 次；Sol 默认 0 次。Balanced 普通章仅可增加 1 次条件式 Sol 审核。多个审稿角色不得每章无差别并行。

## 六角色加载

| 角色 | 何时加载 |
|---|---|
| Chief Editor | 每个任务；判定意图、模式、预算、冲突和发布边界 |
| Story Architect | 总纲、结局、篇章结构、核心人物弧、长期伏笔或重大结构变更 |
| Scene Planner | 把章纲转成 Chapter Contract；普通章默认 Luna |
| Chapter Writer | 合同已确认且 Context Pack 足够时写入草稿 |
| Continuity Manager | 发布前检查事实、时间、认知、物品、伏笔并提出 candidate Delta |
| Prose Editor | 诊断后做定向语言修订；高风险章节才考虑 Sol 终审 |

按需读取 `agents/roles/` 中对应角色合同。只有 Continuity Manager 可提出 State/Canon 变更，而且只能形成 candidate Delta；任何角色都不得直接提升候选事实。

## 单章事务

严格执行：

`context → Chapter Contract → draft → review → candidate Delta → publish → state/summary/handoff`

1. **context**：生成最小 Context Pack，保留来源和认知边界。
2. **Chapter Contract**：确认目的、POV、场景因果、披露边界、章末状态和风险。
3. **draft**：只写入 `novel/drafts/`，不得覆盖非空正式章节。
4. **review**：运行确定性检查、连续性审查和定向文字审查；根本结构问题返回合同阶段。
5. **candidate Delta**：记录候选事实与冲突，不污染 Canon/State。
6. **publish**：仅在正文、合同、Delta、章节 ID 和高严重度冲突均通过或有明确人工豁免后，发布到 `novel/chapters/`。
7. **state/summary/handoff**：确认 Delta 后才同步正式状态、章节摘要、伏笔与当前交接。

**失败边界：** 任一必需检查未通过、候选变更未确认或高严重度冲突未裁决时，停止事务；内容不得进入 `novel/chapters/`、Canonical state、正式 Canon/State，也不得标记章节完成。

## 按任务加载 references

| 当前任务 | 读取 |
|---|---|
| 总纲、结局、篇章与章节里程碑 | `references/planning.md` |
| Chapter Contract、场景链、正文草稿 | `references/chapter-writing.md` |
| 审稿、返修、局部润色 | `references/revision.md` |
| 人物、关系、地点、物品、时间线、伏笔与 Delta | `references/continuity.md` |
| 跨会话恢复、Context Pack、长篇检索 | `references/context-routing.md` |
| 修辞、节奏、叙事距离与章末推进 | `references/literary-techniques.md` |
| 模式、调用预算与模型升级 | `references/model-routing.md` |

只加载当前任务需要的 reference；不要一次读完七份。

## 成本与子代理硬约束

- 每次创建子代理都要显式指定 `model: gpt-5.6-luna`，不得默认继承主会话模型；Sol 只能在命中升级条件并完成事前说明后显式使用。
- 子代理默认使用 `fork_context: false`，仅发送最小 Context Pack；不得复制完整聊天历史。
- 普通章节最多使用 1 个 Luna 写作代理与 1 个 Luna 审校代理，Sol 默认 0 次；默认并发模型子代理不超过 2 个，且不得并行多个同职能代理。
- 同一批材料只允许一个代理完整阅读。并行任务必须有互不重叠的输入范围或写入范围，禁止重复通读、重复评审。
- `validate`、测试、格式检查、Git、索引等确定性工作只用本地工具，不得消耗模型调用。
- 代理超时或中断时复用同一代理，发送最小续写输入；只有无法恢复时才创建替代代理，禁止重新投喂全量上下文。
- 调用 Sol 前向用户说明升级原因、输入范围与预计次数并取得明确同意；用户已明确要求 Sol 时视为已同意该次请求。
- 任务结束时报告实际 Luna/Sol 调用次数，包括 0 次。

## Sol 升级条件

满足任一项时可升级 `gpt-5.6-sol`：影响总纲、结局或长期主线；核心人物动机不可逆变化；重要关系关键转折；重大伏笔埋设、揭露、回收或废弃；多个权威来源冲突；Luna 连续两次不满足结构要求；本地检查发现高严重度矛盾；用户明确要求 Sol。

## 完成清单

- 产物仍处于正确层级：草稿、候选或正式发布。
- 章节完成前运行 `python tools/novel.py validate`，错误已处理或记录明确人工豁免。
- 运行 `python tools/novel.py handoff` 更新精简交接。
- 用户要求备份、会话结束、章节完成或篇章结束时，提醒可选运行 `python tools/novel.py backup`；validate 失败时不得以“已完成”名义备份。
