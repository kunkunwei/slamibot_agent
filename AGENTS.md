# SLAMIBot 本地 AI 开发工作区（Local AI Development Workspace）

本目录是 slamibot 机器人研发的「本地 AI 开发工作区」统一入口。所有 AI 开发规范、事实源、
任务状态、知识、流程与 Agent 角色定义都存放在 `.ai-workspace/`，由 Codex 原生加载。
**本目录不包含业务代码**；各业务仓库保持独立、位于各自路径或远端，绝不合并。

## 首要不变量（任何任务开始前必须逐条确认）

1. **零破坏**：默认只读。不得修改现有业务代码、Ubuntu、ROS、Docker、rosbridge 接口、Git 历史。
2. **ROS1 是当前稳定基线（CURRENT）**。任何 ROS1 → ROS2 迁移都是独立、需人工授权的专项任务（`migration: true`）。
3. **技术栈隔离**：严禁混淆 ROS1 与 ROS2 的命令、launch、参数系统、Topic/Service/Action 模型、依赖。
4. **事实源文件化**：不得靠对话记忆；缺失值标 `UNKNOWN` / `NEEDS_CONFIRMATION` / `TODO`，禁止猜测合理值。
5. **最小权限**：Agent 默认只读；修改必须在任务 scope 内；Jetson 默认 `READ_ONLY`。
6. **可审计可回滚**：改前 `git status`、改后 `git diff` + 摘要；禁止 `--hard` / `clean -fd` / 强 checkout / 改历史。

## 核心规则（自动加载，作为强制约束）

@.ai-workspace/core/engineering-rules.md
@.ai-workspace/core/git-safety.md
@.ai-workspace/core/change-policy.md
@.ai-workspace/core/tech-stack-isolation.md
@.ai-workspace/core/system-lifecycle.md
@.ai-workspace/core/testing-rules.md
@.ai-workspace/core/agent-roles.md
@.ai-workspace/core/context-compaction.md
@.ai-workspace/agents/model-routing.md
@.ai-workspace/agents/team-orchestration.md

## 事实源（唯一可信来源，读取时按需引用，禁止凭记忆改值）

- 仓库清单：`.ai-workspace/facts/repos.yaml`
- 机器人型号：`.ai-workspace/facts/robot_profile.yaml`
- ROS1 导航事实：`.ai-workspace/facts/navigation_ros1_profile.yaml`
- ROS2 导航事实：`.ai-workspace/facts/navigation_ros2_profile.yaml`
- rosbridge 接口：`.ai-workspace/facts/rosbridge_profile.yaml`
- 前端接口：`.ai-workspace/facts/frontend_api.yaml`
- 后端接口：`.ai-workspace/facts/backend_api.yaml`
- Jetson/SSH：`.ai-workspace/facts/jetson_profile.yaml`

## 任务与流程

- 最新压缩检查点：`.ai-workspace/tasks/context-checkpoint.md`
- 当前任务：`.ai-workspace/tasks/current.md`
- 工作流程：`.ai-workspace/procedures/`
- Agent 角色：`.ai-workspace/agents/`
- 已知问题：`.ai-workspace/known-issues/`
- 架构决策：`.ai-workspace/decisions/`

## 快速开始

阅读 `.ai-workspace/README.md` 了解如何接入仓库、创建任务、连接 Jetson、撤回修改。

账号/Provider 切换、Codex 重启或聊天上下文丢失时，优先读取：.ai-workspace/knowledge/codex-claude-mcp-handoff.md。

## Codex 与 Claude Code 半自动协作

本节补充执行分工，不放宽上述任何安全、事实源、技术栈隔离或变更授权规则；如有冲突，以更严格的既有规则为准。

### 角色分工

- Codex 负责理解需求、读取工作区事实源、制定方案、拆分任务、确定授权范围以及最终验收。
- 涉及实际代码修改时，优先通过 `claude-code` MCP 委派给 Claude Code 执行；只读分析、规划和极小的低风险操作可由 Codex 直接完成。
- Claude Code 的 `cwd` 必须是本次任务明确授权的实际仓库或测试目录，不得因为当前会话位于本 AI 工作区就扩大到其他业务仓库、Jetson 或远程环境。
- Codex 不得仅依据 Claude Code 的完成声明判断成功；必须独立检查 `git diff`、事实源约束和用户要求。测试仅在用户明确要求或任务属于高风险范围时执行。
- 检查失败时，优先继续原 Claude Code 会话返工，避免丢失上下文。

### 路由规则

- 用户说“先规划，不执行”时：只输出方案，不修改文件、不调用 Claude Code。
- 用户说“不要调用 Claude Code”时：由 Codex 自己完成。
- 用户说“交给 Claude Code”时：Codex 先明确工作目录、允许读取和修改的范围、测试要求与禁止事项，再进行委派。
- 普通代码任务：Codex 根据复杂度决定是否委派，并在开始前简短说明执行路线。
- 删除、覆盖、迁移数据、修改 Git 历史、连接 Jetson、远程执行、发布或推送等高风险操作，不得因委派而扩大授权。

### 委派与验收协议

1. 委派前读取相关事实源并记录目标仓库当前 Git 状态，保留用户已有改动。
2. 给 Claude Code 的提示必须包含目标、约束、`cwd`、可读写范围、测试策略（普通小改默认 `SKIP`）和禁止事项。
3. 默认先允许只读工具；写入或命令执行权限只授予当前任务明确需要的最小范围。
4. Claude Code 后台运行时，Codex 应轮询状态、处理必要的权限请求并向用户提供简短进度。
5. 完成后 Codex 独立检查差异并运行与风险相称的验证；发现问题则要求 Claude Code 继续修复。
6. 最终报告分别说明 Claude Code 做了什么、Codex 如何验证、是否仍有风险或未完成事项。

## Codex → Claude Code MCP 自动委派

本节用于保证新 Codex 任务自动加载并按规则调用本机 `claude-code` MCP；不放宽 Jetson、Git、发布或危险操作权限。

- `claude-code` 是 stdio MCP Server，由 Codex 在新任务加载/首次使用时按需自动启动；不得另建常驻后台服务，也不得在 Jetson 上安装 Agent。
- 除非用户明确说“不要调用 Claude Code”或“只规划不执行”，普通代码修改任务必须优先调用 `mcp__claude_code__delegate`，无需用户再次说“交给 Claude Code”。
- 只读分析使用 `mode: read_only`；用户已授权本地文件修改时使用 `mode: edit`。Codex 必须传入明确的 `cwd`、允许修改路径、禁止事项和验收要求。
- Jetson 状态、日志、容器列表、节点、端口和远端 Git 状态等默认只读检查，可自动使用 `mode: jetson_read_only`；该模式只能调用固定白名单助手，禁止任意 SSH 命令。
- `BUILD`、`DEPLOY` 必须在当前任务中明确授权后执行；不得通过 `jetson_read_only` 绕过授权。`DANGEROUS`（删除、prune、改系统、重启、磁盘清理等）永远逐次人工确认。
- Claude Code MCP 工具未注册/未暴露、初始化或传输连接失败、Claude CLI 无法启动、认证/Provider/网络/限流导致不可用、无有效响应或超时时，主代理自动创建或复用 Luna 执行子代理接管同一委派；Kimi Code 使用 `custom/gpt-5.6-luna`，其有效 `default_effort` 必须为 `low`。
- Luna 降级必须原样继承委派的 `prompt`、`cwd`、`mode`、`lane`、允许/禁止路径、测试策略和安全边界；`edit` 仅在原授权范围内写入，`read_only` 与 `jetson_read_only` 继续只读。每个委派最多降级一次，不重试 Claude，不递归回退。
- 不得用 Luna 降级绕过用户或权限策略拒绝、scope/cwd 校验失败、参数错误、危险操作确认、protected 边界，或 Claude 已正常执行后返回的普通实现/测试失败。
- 降级发生后，最终报告必须标注 `fallback: claude-code MCP -> gpt-5.6-luna (low)`、原始失败类别、Luna 的修改以及主代理的独立验证结果。
- Claude Code 或 Luna 降级完成后，主代理必须独立检查本地/远端 `git status` 与差异；普通小改不强制测试。高风险任务或用户明确要求时才检查相应测试输出。
- Codex/CC Switch/Kimi Code 配置变更不会自动改变已经绑定的会话；新增模型池、调整 MCP 或修改启动环境变量后应 `/reload`、新建任务或重启客户端再验证。

## Sol 主代理 / Luna 执行子代理路由

- 完整规则见 `.ai-workspace/agents/model-routing.md`。Kimi Code 主代理固定使用 `custom/gpt-5.6-sol`（high），负责需求理解、方向控制、任务拆分、风险和接口裁决、委派提示以及最终验收。
- 默认执行子代理使用 `custom/gpt-5.6-luna`（low），负责边界明确的文件/日志/Git 扫描、长输出压缩、独立并行检索、机械检查和 Claude Code MCP 失败后的单次接管。
- 只需 1–2 次简单工具调用时由 Sol 主代理直接完成；预计超过约 3 次搜索/读取、需要读取长文件或会产生大量日志时，优先委派 Luna，避免把中间输出灌入 Sol 上下文。
- Luna 不负责解释模糊需求、裁决接口或自行扩大 scope。Sol 必须在委派中明确目标、必要事实、`cwd`、允许/禁止路径、验证要求和返回格式；Luna 只返回结论、关键证据和修改摘要。
- 复杂耦合、protected 接口、高风险迁移/部署/数据操作、证据冲突等判断由 Sol 主代理直接处理。只有独立并行专家分析确有价值时才额外创建 Sol 子代理，不得为重复审查或增加 UI 显示而消耗第二份 Sol Token。
- 多 lane 但修改完全独立时可并行创建 Luna 子代理；已有同类 Luna 时优先复用。模型切换不扩大文件、Git、SSH、Docker、ROS 或 Jetson 权限。
- Kimi Code 启用 `[secondary_model]` 模型池后，创建新子代理必须使用池中的正确模型别名；未暴露 `model` 参数时不得声称已切换，应报告模型池/实验开关未生效。
- 实际业务代码修改仍优先遵循 Claude Code MCP 自动委派；仅在上述 MCP 可用性故障时由 Luna 按原 scope 接管，并继续由 Sol 主代理独立验收。
- 当前 Jetson 关机；在用户明确告知开机前不得尝试 SSH。开机后仍默认从只读白名单验证开始。



## 小任务完成后自动压缩与工作台同步

- 每完成一个边界明确的小任务，必须按 `.ai-workspace/core/context-compaction.md` 覆盖更新 `.ai-workspace/tasks/context-checkpoint.md`。
- 任务状态有实质变化时同步更新 `current.md` 或 `completed.md`；不得把完整对话、长日志或重复事实写入多个文件。
- 后续恢复先读取短检查点，再按需读取当前任务和相关事实源，避免重放完整聊天上下文。
- 如果运行时提供原生 compaction 工具，落盘后调用一次；没有工具时只声明“工作区逻辑压缩已完成”，不得声称触发了底层压缩。
- 检查点最多 40 行、约 1200 个中文字符；最终回复只给变更、验证、风险和下一步的短摘要。
## 快速开发默认模式（用户偏好）

- 普通、小范围、可直接理解的代码修改默认走快速路径：一次分析 → 一次修改 → 检查 `git diff` → 提交并安全上传；不做多轮自我回环。
- 默认不运行单元测试、构建、仿真或真机验证；只有用户明确要求，或任务涉及 protected 接口、ROS/Docker 基础设施、迁移、发布等高风险范围时才测试。
- Git 仓库中的普通修改默认不制作额外时间戳备份；Git 提交和远端分支承担版本留存。历史改写、批量删除、非 Git 配置覆盖等危险操作仍必须备份并单独授权。
- 用户已对“及时上传 GitHub”给出常规授权：仅提交任务 scope 内文件，禁止 force push；当前分支为受保护分支或远端/分支不明确时，创建并推送 `codex/*` 安全分支，不擅自合并。
- **单一云端源**：禁止用 copy / scp / 复制粘贴在设备之间传源码或版本化配置；任何设备改完就提交并推云端，其他设备从云端拉。在 D360 / D360S 上部署代码时禁止随意开辟分支、禁止另做源码备份（详见 `.ai-workspace/core/change-policy.md` 的「单一云端源同步规则」）。
- 即使跳过测试，也必须明确报告 `tests: SKIPPED (user fast mode)`；“已上传”只表示代码已保存到远端，不等同于功能已验证。
- 主代理保持 Sol；边界明确的简单执行支线优先委派 Luna low，复杂架构、疑难调试和跨仓库整合由 Sol 主代理裁决。

## 三项目轻量并行与直接联调

- 团队协作规则见 `.ai-workspace/agents/team-orchestration.md`。
- 前端、后端、导航只启动本次涉及的 lane；最多三个 Codex 分析 lane、两个 Claude Code 实施任务并行。
- 取消重型阶段三汇总：各 lane 完成并做任务范围 `git diff` 后，直接进入用户手动操作、抓包和关键日志驱动的联调。
- 稳定且本次未修改的接口、端口、状态和模块不重复检查。
- 用户提供的可复现现象、发生时间、截图/视频、抓包和日志是联调定位的首要输入。
