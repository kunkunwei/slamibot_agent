# Chapter Writing Reference

## Purpose

在不越过已确认结构和认知边界的前提下，把章节里程碑转换为具备生命周期的 Chapter Contract、因果连续的场景链和位于草稿区的正文。

## Required inputs

- 当前篇章目标、章节里程碑和上一章结束状态。
- 最小 Context Pack：相关 Canon、已确认 State、活跃伏笔、近期摘要及必要原文。
- 作品 style card、人物声音、禁用表达和目标字数。
- 已选择的 fast、balanced 或 premium 模式与风险等级。

## Procedure

1. 填写 Chapter Contract 的全部字段：chapter_id、arc_id、status、confirmed_by、confirmed_at、confirmation_basis、叙事目的、POV、叙事距离、开场状态、必须发生事件、场景顺序与因果、人物及目标、允许公开信息、禁止提前揭露信息、主线/支线/人物弧推进、伏笔动作、情绪曲线、节奏、文学手法、保护事实、章末状态与钩子、预计字数、风险等级。
2. 执行合同生命周期：`candidate → confirmed` 需要明确确认者、确认时间和确认依据；`candidate → retired` 表示停止使用。candidate 可写试稿，但只有 confirmed 可进入正式写作事务，未确认合同对应的试稿不得发布。
3. 把合同拆为场景链；每场写清进入状态、人物目标、阻力、选择、行动、即时结果、反应、信息变化和下一场触发。
4. 使用行动—反应循环：行动必须改变局面；反应包含感受、判断和下一选择，避免事件堆叠而人物不作决定。
5. 执行行为与环境连续性检查：每次转场要有目标、声音、信息或身体需求触发，写出必要移动或明确时间省略，并在到达后建立空间锚点；逐动作追踪体位、伤势、疲劳、呼吸、持物状态以及火、烟、水、光线、门窗等环境变化，禁止镜头瞬移、道具凭空出现和状态重置。
6. 锁定 POV 与认知边界：只叙述视角人物可感知、可回忆、可推断的内容；他人内心必须通过行为、语言或已授权视角表现。
7. 把认知变更作为连续性一等数据：记录谁在何场景知道、误信、怀疑或遗忘了什么，并交由 `knowledge_changes` 审核，不得只埋在摘要文字中。
8. 只选择 2–4 种服务本章目的的文学手法，遵守作品既有文风。
9. 所有章节路径从 `chapter_id` 派生：合同 `novel/plans/<chapter_id>.md`，草稿 `novel/drafts/<chapter_id>.md`，正式正文 `novel/chapters/<chapter_id>.md`，摘要 `novel/summaries/chapters/<chapter_id>.md`，Delta `novel/state/deltas/<chapter_id>.json`。正文必须先进入草稿路径，不得直接写正式正文路径。
10. 写完逐项对照合同，标出偏离、原因和需要返回规划阶段的问题，不自行重做根本结构；审查后才生成 candidate Delta。

## Outputs

- 字段完整、生命周期可机读且可审查的 Chapter Contract。
- 带场景因果、披露控制和章末钩子的章节草稿。
- 包含 `knowledge_changes` 输入的合同偏离清单、未决问题和审查重点。
- 由同一 `<chapter_id>` 派生的 plan、draft、chapter、summary 和 Delta 路径清单。

## Stop/escalate conditions

- Contract 缺失、互相矛盾、状态不是 confirmed 或与高权威事实冲突时，停止正式写作事务；candidate 仅可试稿。
- 必须依赖视角人物不知道的信息才能推进时，返回场景规划并记录候选认知变化。
- 需要改变结局、长期主线、核心动机或重大伏笔时升级 Sol。
- 非空正式章节已存在时不得覆盖；改稿进入 `novel/drafts/<chapter_id>.md` 或快照流程。
