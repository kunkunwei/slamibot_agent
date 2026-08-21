# Codex Subagent 模型路由：Sol / Luna

本文件定义 Codex 原生 subagent 的模型分工。它只决定 Codex 子代理使用哪个模型；Claude Code 仍通过 `claude-code` MCP 独立委派。

## 默认分工

| 任务类型 | 模型 | 建议 reasoning | 说明 |
|---|---|---|---|
| 日常主协调、任务拆分、工具调用、结果汇总 | `gpt-5.6-luna` | `low` | 默认主模型；优先速度和低成本 |
| Explorer 只读扫描、资料整理、独立并行检索、低风险验证 | `gpt-5.6-luna` | `minimal` / `low` | 边界清楚的并行支线可创建或复用 Luna subagent |
| Implementer | Claude Code MCP；极小本地文档操作可用 Luna | `low` | 写入必须受任务 scope 限制；实际业务代码修改优先走 Claude Code MCP |
| Expert / Escalation | `gpt-5.6-sol` | `medium` / `high` | 仅用于复杂架构、疑难根因、跨仓库整合和高风险决策 |
| Validator | 默认 Luna；高风险且确有必要时才用 Sol | `low` / `medium` | 普通任务不启动例行 Sol 最终审查 |

## 自动切换规则

1. 默认主任务使用 `gpt-5.6-luna`。Luna 负责日常需求理解、文件/日志/Git 检查、lane 拆分、工具调用、Claude Code MCP 委派、任务范围 diff 和简短汇总。
2. 普通任务的 Sol 请求目标为 0。不得仅因为任务开始、工具返回、Claude Code 完成或需要最终总结而调用 Sol。
3. 只有满足下列任一条件时，才显式创建 `gpt-5.6-sol` subagent：
   - 跨前端、后端、导航仓库的架构决策或复杂接口冲突；
   - ROS/Docker/rosbridge protected 接口、高风险迁移、部署或数据操作；
   - Luna 已完成一次边界明确的定位，但仍无法确定根因或存在多个高风险方案；
   - 用户明确要求使用 Sol 深入分析。
4. Sol 委派必须包含一个边界明确的问题和所需事实，默认只咨询一轮；不得让 Sol执行例行文件搜索、机械 Git 检查、普通 diff 转述或常规最终审查。
5. 独立且非阻塞的批量扫描可显式创建或复用 `gpt-5.6-luna` subagent。已有同类 Luna 时优先复用，不为增加 UI 显示次数重复创建。
6. 紧急阻塞步骤由 Luna 主 Agent 本地处理，不为了形式化分工等待 subagent。
7. 不在运行中的 subagent 内“热切换”模型；需要升级时新建 Sol 子代理并只传递必要上下文。
8. 任何模型均继承本工作区安全规则；模型切换不扩大文件、Git、SSH、Docker、ROS 或 Jetson 权限。
9. Jetson 未开机或用户未声明已上线时，不进行 SSH 连通性重试。上线后默认仅执行 `READ_ONLY` 白名单检查。
## 与 Claude Code MCP 的关系

- Codex subagent：用于 Codex 内部并行分析、实现支持与验证，模型可选 Sol/Luna。
- Claude Code MCP：用于把实际代码任务委派给 Claude Code；`cwd`、读写 scope、测试和禁止事项必须明确。
- 推荐链路：Luna 主 Codex 轻量协调 → Luna Explorer 按需并行扫描 → Claude Code MCP 实施 → 必要时单轮 Sol 专家咨询 → 直接进入用户手动现象/抓包驱动的联调。

## 快速开发路由

- 一行/小范围修改、明确文件和明确预期：优先 Luna，`reasoning_effort: minimal` 或 `low`。
- Luna 默认单次实施，不自行扩展测试、重构、备份或多轮修复。
- Sol 只用于复杂架构、疑难根因、跨仓库整合、高风险变更和最终复杂审查。
- 工具调用和流程长度通常比模型推理速度更影响总耗时，因此快速任务必须同时减少非必要工具步骤。

## 联调优先规则

- 各 lane 完成后不启动独立 Validator 做全量重复检查。
- Codex 只确认 diff 未越过本次任务范围，然后直接进入联调。
- 优先依据用户手动测试现象、HTTP/WebSocket 抓包和关键 ROS/服务日志定位所属 lane。
- 稳定且未修改的模块不重新分析；修复只返回故障所属 lane，一次修改后再次等待用户观察。
