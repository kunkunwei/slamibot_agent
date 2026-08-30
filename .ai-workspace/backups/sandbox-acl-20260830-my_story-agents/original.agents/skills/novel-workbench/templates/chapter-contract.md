# Chapter Contract: ch-0001 名单上的死者

- schema_version: 0.1
- chapter_id: ch-0001
- arc_id: arc-001
- status: candidate
- confirmed_by: null
- confirmed_at: null
- confirmation_basis: not-confirmed
- allowed_statuses: candidate|confirmed|retired
- formal_transaction_status: confirmed
- trial_draft_statuses: candidate|confirmed
- publishable_contract_statuses: confirmed
- mode: balanced
- risk_level: medium
- target_words: 3800
- draft_path: novel/drafts/ch-0001.md
- publish_path: novel/chapters/ch-0001.md

## Lifecycle

| status | Trial draft | Formal writing transaction | Publish eligibility |
|---|---|---|---|
| candidate | 允许写入 drafts 试稿 | 不允许 | 不允许 |
| confirmed | 允许 | 允许进入 context → contract → draft → review 事务 | 审查和 Delta 门槛通过后允许 |
| retired | 不允许继续 | 不允许 | 不允许 |

`candidate → confirmed` 必须填写 `confirmed_by`、`confirmed_at` 和 `confirmation_basis`；`candidate → retired` 表示合同弃用。只有 `confirmed` 合同可进入正式写作事务。未确认合同可以试稿，但试稿不得发布到正式章节。

## Narrative purpose

让主角主动接受王城资格审查，建立“身份安全换取行动资格”的核心代价，并在章末抛出已故者姓名。

## POV and narrative distance

第三人称限知，POV 为主角林砚；审查场景保持近距离，制度说明使用短暂中距离概述。

## Opening state

林砚持临时通行证抵达审查厅，知道审查可能暴露假身份，但不知道名单已被篡改。

## Must happen

1. 林砚确认不接受审查就无法进入王城核心区。
2. 他观察并利用审查流程中的一处规则缝隙。
3. 他主动签署责任书，而非被迫推进剧情。
4. 章末名单出现三年前已确认死亡的顾沉舟。

## Scene chain

| Scene | Goal | Obstacle | Choice/action | Result/reaction | Next trigger |
|---|---|---|---|---|---|
| scene-01 | 进入审查厅 | 临时证件权限不足 | 林砚公开要求复核 | 获得一次听证，也引来记录官注意 | 被要求签责任书 |
| scene-02 | 保住匿名性 | 责任书要求真实来源 | 林砚用规则允许的担保编号替代 | 资格暂时保留，风险转移给担保人 | 名单开始唱名 |
| scene-03 | 判断名单异常 | 不能公开表现认识死者 | 林砚压住反应并记下顺序 | 他决定留在王城追查 | 顾沉舟姓名被念出 |

## Characters and goals

- 林砚：进入核心区，同时隐藏真实来历。
- 记录官沈澜：确保流程无漏洞，并判断林砚是否值得继续观察。
- 担保人周策：不在场；其编号成为林砚可承担的关系债。

## Information boundaries

- allowed_to_reveal: 审查流程、担保编号规则、顾沉舟姓名。
- forbidden_to_reveal: 名单篡改者、顾沉舟姓名出现的机制、林砚旧名。
- pov_knowledge_limit: 林砚只知道顾沉舟三年前死亡，不知道尸体记录是否被人动过。

## Threads and hooks

- main_plot: 取得王城行动资格。
- subplot: 周策担保产生的人情债。
- character_arc: 林砚第一次为长期目标主动接受可追踪风险。
- foreshadowing: 唱名前记录官短暂停顿；名单纸张有新旧两种墨色。
- hook: 顾沉舟姓名被念出后，有人从候审队伍中回答“到”。

## Emotional curve and pacing

克制警惕 → 短暂掌控 → 代价落地 → 异常升级；前两场中速，唱名段落加速，最后三段缩短。

## Literary techniques

- 信息差：读者与林砚同时知道死者身份，但不知道应答者是谁。
- 对话潜台词：记录官以流程问题测试林砚来历。
- 段落节奏：章末连续短段压缩反应时间。

## Protected facts

- 顾沉舟的死亡是已确认事实。
- 林砚不得知道名单篡改者身份。
- 沈澜本章不公开敌友立场。

## Ending state

林砚取得临时审查资格，身份风险上升，并决定追查名单异常。

## Review focus

POV 不越界；规则缝隙可理解；签署责任书是主动选择；章末钩子不提前解释。
