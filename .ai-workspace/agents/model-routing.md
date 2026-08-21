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
2. 单 lane 普通任务的 Sol 请求目标为 0。不得仅因为任务开始、工具返回、Claude Code 完成或需要最终总结而调用 Sol。
3. 满足以下任一客观条件时，必须显式创建或复用 `gpt-5.6-sol` subagent，不得等待用户点名：
   - 前端、后端、导航中至少两个 lane 存在相互依赖，需要端到端联调或共同解释同一故障；
   - 故障可能跨 API、HTTP/WebSocket、rosbridge、ROS Topic/Service/Action、容器或网络层传播，需要建立跨层因果链；
   - 需要修改、裁决或确认 API/消息字段/状态码/端口/Topic/Service/Action 等接口契约或 protected 接口；
   - 涉及高风险迁移、部署、数据操作或跨仓库架构决策；
   - Luna 已完成一次定位，但仍有多个根因假设、证据互相矛盾或无法确定根因；
   - 用户明确要求使用 Sol。
4. 触发复杂条件后，Luna 只收集能够界定问题的最小事实，然后必须在给出根因结论或实施方案前调用 Sol；Sol 不是等待 Luna 失败后才考虑的可选项。
5. 多 lane 修改若完全独立、无共享接口且无需解释同一端到端现象，可以继续由 Luna 协调，不触发 Sol。
6. Sol 委派必须包含一个边界明确的问题、相关事实和期望决策，默认先咨询一轮；只有新增证据实质改变判断时才继续原 Sol 会话。
7. 不得让 Sol 执行例行文件搜索、机械 Git 检查、普通 diff 转述、Claude Code 结果转述或常规最终审查。
8. 独立且非阻塞的批量扫描可显式创建或复用 `gpt-5.6-luna` subagent。已有同类 Luna 时优先复用，不为增加 UI 显示次数重复创建。
9. 不在运行中的 subagent 内“热切换”模型；复杂升级时新建或复用 Sol 子代理并只传递必要上下文。
10. 任何模型均继承本工作区安全规则；模型切换不扩大文件、Git、SSH、Docker、ROS 或 Jetson 权限。
11. Jetson 未开机或用户未声明已上线时，不进行 SSH 连通性重试。上线后默认仅执行 `READ_ONLY` 白名单检查。
## 与 Claude Code MCP 的关系

- Codex subagent：用于 Codex 内部并行分析、实现支持与验证，模型可选 Sol/Luna。
- Claude Code MCP：用于把实际代码任务委派给 Claude Code；`cwd`、读写 scope、测试和禁止事项必须明确。
- 推荐链路：Luna 主 Codex 轻量分诊 → 复杂跨 lane 联调时立即调用 Sol 建立因果链 → Luna/Claude Code 按 lane 实施 → 直接进入用户手动现象/抓包驱动的联调。

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
