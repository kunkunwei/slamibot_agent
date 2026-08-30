# Continuity Reference

## Purpose

依据可追溯证据检查人物、关系、认知、地点、物品、时间线与伏笔，并只以 candidate Delta 提出潜在正式变更。

## Required inputs

- 当前草稿、已确认 Chapter Contract、相关已发布正文和章节摘要。
- 相关 Canon、已确认 Delta/State、人物知识状态、物品状态、时间线和伏笔表。
- 来源文件路径、章节 ID、场景 ID 与当前人工豁免记录。

## Procedure

1. 按权威顺序裁决：用户确认 > 已发布正文 > Canon > 已确认 Delta/State > 大纲 > 摘要 > 推断。
2. 将草稿中的新内容分类为 facts、character_changes、relationship_changes、knowledge_changes、location_changes、item_changes、timeline_events 和 hook_changes；认知变更是连续性一等数据，必须记录认知主体、旧认知、新认知、来源场景和生效章节，不能只写入摘要。
3. 每个变更对象统一使用审核生命周期：`proposed → accepted` 或 `proposed → rejected`，并保留 reviewed_by、reviewed_at、review_basis。accepted 只表示对象审核通过，不代表已经写入正式状态。
4. Delta 顶层生命周期为 `candidate → confirmed`、`candidate → rejected`、`confirmed → applied`。只有 applied 表示已完成正式 State/Canon 同步；candidate 或 confirmed 中的事实都不得被当成已应用事实。
5. 检查人物：死亡/失踪/伤势/能力/位置/目标/认知；已确认死亡后的出场必须有复活、回忆、伪装或人工豁免证据。
6. 检查物品：持有者、位置、数量、损坏/销毁状态和转移链；销毁后使用必须有解释或冲突记录。
7. 检查时间线与地点：先后关系、旅行时间、同时事件、昼夜、年龄与场景位置不得互斥。
8. 检查伏笔与承诺：埋设、强化、误导、揭露、回收、废弃；回收不得早于埋设，延期要记录叙事债务。
9. 发现冲突时生成结构化对象：id、severity、claim、evidence、affected_chapters、status、waiver。severity 仅可为 low、medium、high、critical；状态按 `open → waived` 或 `open → resolved` 转换。waived 必须记录 reason、approved_by、approved_at；不得用空豁免绕过检查。
10. 只有 Continuity Manager 可生成 State/Canon 变更提案。高或 critical 的 open conflict 阻止 Delta confirmed、正文发布和状态应用；规则检查、Sol 裁决或用户确认只能推动候选生命周期，不能跳过 applied 事务。

## Outputs

- 完整的 candidate Delta，含来源、统一审核元数据、knowledge_changes 和状态转换记录。
- 连续性检查报告和结构化 conflicts；无冲突时也保留空数组结构。
- 需要人工豁免、Sol 裁决或用户确认的项目。
- confirmed 后等待正式应用的输入，或 applied 后可供 state/summary/handoff 使用的同步结果。

## Stop/escalate conditions

- 多个高权威来源互相冲突时停止发布并升级 Sol 或用户裁决。
- 出现重要人物死亡、物品销毁、重大关系转折、认知边界改变或伏笔回收时至少进入 balanced 风险审查。
- 缺少原文证据却只能依赖摘要或推断时，不得把 proposed 变更转为 accepted。
- high 或 critical 的 open conflict 未 resolved/waived 时，Delta 不得 confirmed 或 applied，正文不得发布。
