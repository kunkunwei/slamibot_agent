# 主代理 / 子代理模型路由：Sol / Luna

本文件定义 Kimi Code/Codex 的模型分工，以及 Claude Code MCP 不可用时的编排层降级。模型切换由主代理运行时负责；MCP Server 本身不负责启动或选择子代理。

## 默认分工

| 任务类型 | 模型 | reasoning | 说明 |
|---|---|---|---|
| 主代理：需求理解、方向控制、任务拆分、风险/接口裁决、最终验收 | `gpt-5.6-sol` | `high` | Kimi Code 别名 `custom/gpt-5.6-sol`；保持完整用户上下文 |
| 执行子代理：文件/日志/Git 扫描、长输出压缩、独立检索 | `gpt-5.6-luna` | `low` | Kimi Code 别名 `custom/gpt-5.6-luna`；默认 secondary model |
| Implementer | Claude Code MCP；可用性故障时 Luna 接管 | `low` | 写入受原任务 scope 限制；每个委派最多降级一次 |
| 独立 Expert 子代理 | `gpt-5.6-sol` | `high` | 仅当额外并行复杂分析确有价值；不得重复主代理判断 |
| Validator | 默认 Luna；主代理 Sol 负责最终裁决 | `low` / `high` | 普通任务不启动例行 Sol 子代理审查 |

## Kimi Code 运行时配置

- 顶层 `default_model = "custom/gpt-5.6-sol"`，主代理保持 Sol high。
- `[secondary_model].default_model = "custom/gpt-5.6-luna"`，模型池同时列出 Luna 和 Sol；Luna 模型条目的有效 `default_effort = "low"`，Sol 保持 `high`。
- 必须启用 `KIMI_CODE_EXPERIMENTAL_SECONDARY_MODEL=1`。模型池生效后，`Agent`/`AgentSwarm` 才会暴露 `model` 参数；未暴露时不得声称已切换模型。
- 不设置 `[secondary_model].default_effort = "low"`，否则显式选择的 Sol 子代理也会被压成 low。

## 委派规则

1. Sol 主代理始终负责理解用户需求、确认边界、制定方案、判断风险、编写委派提示和最终验收；不得把模糊需求原样丢给 Luna 解释。
2. 只需 1–2 次简单工具调用时由 Sol 直接完成，避免子代理启动开销。
3. 预计超过约 3 次搜索/读取、需要读取长文件/长日志、批量扫描多个独立路径，或中间输出会明显污染主上下文时，优先创建或复用 Luna 子代理。
4. Luna 委派必须包含目标、最小必要事实、`cwd`、允许/禁止路径、权限模式、验证要求和返回格式；Luna 不裁决接口、不扩大 scope、不做无关重构，只返回结论、关键证据和修改摘要。
5. 多 lane 完全独立、无共享接口和共同因果链时，可并行创建 Luna 子代理；已有同类 Luna 时优先复用。
6. 复杂耦合、protected 接口、高风险迁移/部署/数据操作、跨仓库架构和证据冲突，由 Sol 主代理直接建立因果链并作出决策。
7. 只有独立并行专家分析确有价值或用户明确要求时才额外创建 Sol 子代理；不得让 Sol 子代理执行例行搜索、机械 Git 检查、普通 diff 转述、Claude Code 结果转述或常规最终审查。
8. 子代理模型在创建时绑定；运行中不热切换。任何模型均继承工作区安全规则，模型切换不扩大文件、Git、SSH、Docker、ROS 或 Jetson 权限。
9. Jetson 未开机或用户未声明已上线时，不进行 SSH 连通性重试；上线后默认仅执行 `READ_ONLY` 白名单检查。

## Claude Code MCP 失败降级

1. 以下可用性故障触发降级：MCP 工具未注册或未暴露、初始化/传输连接失败、Claude CLI 无法启动、认证/Provider/网络/限流不可用、无有效响应或超时。
2. Sol 主代理自动创建或复用 Luna 执行子代理；Kimi Code 绑定 `custom/gpt-5.6-luna`，由模型条目保证 effective effort 为 low，并原样传递 `prompt`、`cwd`、`mode`、`lane`、允许/禁止路径、测试策略和验收要求。
3. `edit` 仅在原授权 scope 内实施；`read_only` 和 `jetson_read_only` 继续只读。每个委派最多降级一次，不重试 Claude，不递归回退。
4. 用户或权限策略拒绝、scope/cwd 校验失败、参数错误、危险操作确认、protected 边界，以及 Claude 已正常执行后的普通实现/测试失败，不属于可用性故障，禁止借降级绕过。
5. 最终报告必须包含 `fallback: claude-code MCP -> gpt-5.6-luna (low)`、原始失败类别、Luna 的修改和 Sol 主代理的独立验证结果。

## 推荐链路

Sol 主代理理解需求并确定边界 → 边界明确的大量扫描交给 Luna low → 实际代码优先由 Claude Code 按 lane 实施 → MCP 可用性故障时 Luna low 按原 scope 单次接管 → Sol 检查任务范围 diff → 进入用户手动现象/抓包驱动的联调。

## 联调优先规则

- 各 lane 完成后不启动独立 Validator 做全量重复检查。
- Sol 主代理只确认 diff 未越过本次任务范围，然后直接进入联调。
- 优先依据用户手动测试现象、HTTP/WebSocket 抓包和关键 ROS/服务日志定位所属 lane。
- 稳定且未修改的模块不重新分析；修复只返回故障所属 lane，一次修改后再次等待用户观察。
