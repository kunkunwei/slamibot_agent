# Codex / Claude Code / Sol-Luna 恢复交接

> 更新日期：2026-08-19  
> 用途：切换 GPT 账号、CC Switch Provider、重启 Codex 或丢失聊天上下文后，从本文件恢复工作状态。  
> 安全：本文件不保存 API Key、私钥或完整公钥内容。

## 新会话第一句话

在 Codex 中打开 `F:\slamibot_agent`，发送：

```text
请先读取 AGENTS.md、.ai-workspace/knowledge/codex-claude-mcp-handoff.md 和当前任务事实源；先只读检查配置，不连接 Jetson，不覆盖已有修改。
```

## 当前已配置状态

### Kimi Code 主从模型配置

- 配置：`C:\Users\kun\.kimi-code\config.toml`。
- 主代理：`custom/gpt-5.6-sol`，effective effort `high`；负责需求理解、方向控制、风险/接口裁决、委派和最终验收。
- 默认子代理：`custom/gpt-5.6-luna`，effective effort `low`；负责文件/日志/Git 扫描、长输出压缩、独立检索和明确范围内执行。
- `[secondary_model]` 模型池同时包含 Luna 和 Sol；Windows 用户环境变量 `KIMI_CODE_EXPERIMENTAL_SECONDARY_MODEL=1` 必须生效，`Agent`/`AgentSwarm` 才会暴露 `model` 参数。
- 配置或环境变量变化后运行 `/reload` 或新建 Kimi Code 进程；当前已绑定的子代理不热切换。可用 `/secondary-model`（别名 `/subagent-model`）确认新子代理默认模型。

### Codex 手动配置档

- CLI 配置档：
  - `C:\Users\kun\.codex\sol.config.toml`
  - `C:\Users\kun\.codex\luna.config.toml`
- 手动启动：

```powershell
codex -p sol -C F:\slamibot_agent
codex -p luna -C F:\slamibot_agent
```

账号或 Provider 切换后，先确认上述两个模型仍被当前 Provider 支持，不要直接覆盖整个 Kimi/Codex 配置文件。

### Sol / Luna 自动路由

完整规则：`.ai-workspace/agents/model-routing.md`

- Sol 是默认主协调模型，保持完整用户上下文，负责需求理解、任务边界、复杂因果、风险裁决和最终验收。
- 1–2 次简单工具调用由 Sol 直接完成；超过约 3 次搜索/读取、长文件/长日志或独立并行扫描优先委派 Luna low。
- Luna 不解释模糊需求、不裁决接口、不扩大 scope；Sol 的委派必须包含目标、最小必要事实、`cwd`、允许/禁止路径、权限、验证和返回格式。
- 复杂耦合、接口契约/protected 接口、高风险迁移/部署/数据操作和证据冲突由 Sol 主代理直接处理；只有额外独立专家分析确有价值时才创建 Sol 子代理。
- 实际业务代码修改仍优先委派 Claude Code MCP；仅在 MCP 可用性故障时由 Luna low 按原 scope 单次接管，Sol 主代理独立验收。
- 模型切换不扩大 SSH、Docker、ROS、Git 或文件权限；MCP 失败不取消复杂度和权限门禁。


### 小任务后的上下文压缩

- 每完成一个小任务，覆盖更新 `.ai-workspace/tasks/context-checkpoint.md`，最多 40 行、约 1200 个中文字符。
- 状态变化同步写入 `current.md` 或 `completed.md`；不复制完整聊天和长日志。
- 新任务恢复顺序：`AGENTS.md` → `context-checkpoint.md` → `current.md` → 相关 facts/known-issues。
- 有原生 compaction 工具时落盘后调用；没有时执行工作区逻辑压缩并如实说明。
### Claude Code MCP

- MCP 名称：`claude-code`
- Codex 注册配置：`C:\Users\kun\.codex\config.toml`
- Server：`.ai-workspace/mcp/claude-code-delegate.cjs`
- Jetson 只读助手：`.ai-workspace/mcp/jetson-readonly.cjs`
- 工具名：`mcp__claude_code__delegate`
- 模式：
  - `read_only`：本地只读分析
  - `edit`：任务已授权范围内修改
  - `jetson_read_only`：固定 SSH 白名单只读检查

MCP 是 stdio 按需启动，不需要常驻服务。配置不会热加载：修改配置或切换账号后，应重启 Codex 或新建任务；首次委派时自动启动 MCP。

#### MCP 不可用时的自动降级

- 触发：工具未注册/未暴露、MCP 初始化或传输连接失败、Claude CLI 无法启动、认证/Provider/网络/限流不可用、无有效响应或超时。
- 动作：Sol 主代理自动创建或复用 Luna 执行子代理；Kimi Code 绑定 `custom/gpt-5.6-luna`，由模型条目保证 effective effort 为 low，并原样传递原委派的 `prompt`、`cwd`、`mode`、`lane`、允许/禁止路径、测试策略和验收要求。
- 限制：每个委派最多降级一次；不重试 Claude，不递归回退；`edit`、`read_only`、`jetson_read_only` 的权限语义保持不变。
- 禁止绕过：用户/权限策略拒绝、scope/cwd 校验失败、参数错误、危险操作确认、protected 边界，以及 Claude 已正常执行后的普通实现/测试失败。
- 报告：写明 `fallback: claude-code MCP -> gpt-5.6-luna (low)`、原始失败类别、Luna 修改和 Sol 主代理独立验证结果。
- 实现位置：这是主代理编排层规则；不要修改 MCP Server 让它反向启动子代理，因为 MCP 未注册或失联时 Server 无法承担回退。

检查注册状态：

```powershell
$env:CODEX_HOME='C:\Users\kun\.codex'
$env:HOME='C:\Users\kun'
codex mcp list
```

预期：`claude-code` 状态为 `enabled`。

## Jetson / SSH 交接

当前状态（2026-08-20 15:22:32 CST）：Jetson 已开机，LAN SSH 已由 Codex 直接实测成功，返回 `host=ubuntu`、`user=jetson`。新会话不得继续使用“Jetson 已关机”的旧结论。

事实源：`.ai-workspace/facts/jetson_profile.yaml`  
详细操作手册：`.ai-workspace/procedures/jetson-ssh-connection.md`

连接优先级：

1. **首选且已确认**：LAN `jetson@192.168.31.135:22`。
2. 热点 `jetson@192.168.117.6:22`：`NEEDS_CONFIRMATION`。
3. 公网 `root@116.148.216.66:30046`：2026-08-20 连续超时，当前只作备用；公网超时不代表 Jetson 离线。

Windows 已确认命令：

```powershell
ssh -F NUL -i "C:\Users\kun\.ssh\id_rsa" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 jetson@192.168.31.135
```

- `-F NUL`：绕过可能含旧代理/公网映射的 SSH config。
- Windows 私钥：`C:\Users\kun\.ssh\id_rsa`
- known_hosts：`C:\Users\kun\.ssh\known_hosts`
- Jetson 公钥位置：`~/.ssh/authorized_keys`
- Claude Code `jetson_read_only` 或白名单助手若因本地进程权限失败，不得误判为 Jetson 离线；在用户已授权 SSH 的任务中，由 Codex 使用 `functions.exec_command` + `require_escalated` 执行同一条受限只读 SSH 命令。

原 Claude 交接记录：

```text
C:\Users\kun\.claude\projects\F--slamibot-agent\memory\handoff-2026-08-18-repo-upload.md
```

其中第 38、39、81 行附近记录了免密 SSH、公钥和连通性自测说明。

Jetson 当前已开机。优先直接验证 LAN SSH：

```powershell
ssh -F NUL -i "C:\Users\kun\.ssh\id_rsa" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 jetson@192.168.31.135 "hostname; whoami; date"
```

白名单助手仅作为本地进程权限允许时的补充：

```powershell
node F:\slamibot_agent\.ai-workspace\mcp\jetson-readonly.cjs identity
node F:\slamibot_agent\.ai-workspace\mcp\jetson-readonly.cjs docker-ps
```

权限分级：

- `READ_ONLY`：固定白名单可执行。
- `BUILD` / `DEPLOY`：必须由当前任务明确授权。
- `DANGEROUS`：删除、prune、改系统、重启、磁盘清理等永远逐次人工确认。

## 切换账号后的恢复检查

1. 打开工作目录 `F:\slamibot_agent`。
2. 先读取本文件和 `AGENTS.md`。
3. 检查 `C:\Users\kun\.codex\config.toml` 是否仍保留 `mcp_servers.claude-code`。
4. 运行 `codex mcp list`，确认 `claude-code enabled`。
5. 检查 Sol/Luna 配置档是否存在。
6. 新建任务，做一次本地 `read_only` MCP 冒烟测试。
7. Jetson 未开机时跳过所有 SSH 测试。
8. 不覆盖已有未提交修改；普通任务按快速模式提交并安全推送，禁止 force push 和修改 Git 历史。

## 安全待办

`C:\Users\kun\.codex\config.toml` 曾发现明文 API Key。不要把它复制进交接文档、Git 或聊天；应尽快轮换，并改用安全环境变量或凭据管理方式。

## 默认快速开发偏好

- 普通小改优先 Luna，单次完成。
- 默认不备份、不测试、不构建、不自动修复回环。
- 最低检查：`git status -sb` + 任务范围内 `git diff`。
- 结果标记：`tests: SKIPPED (user fast mode)`。
- 修改完成后及时 commit/push；保护分支或目标不明确时推送 `codex/*` 分支，不直接更新主分支。
- 高风险、历史改写、批量删除、系统/Jetson/Docker 基础设施修改不适用快速模式。

## 三项目团队模式

规则：`.ai-workspace/agents/team-orchestration.md`

- lane：`frontend`、`backend`、`navigation`。
- Claude Code MCP 默认最大并发 2，额外任务自动排队。
- 不做重型阶段三汇总；任务范围 diff 后直接联调。
- 用户手动测试现象、时间点、截图/视频、HTTP/WebSocket 抓包和关键 ROS 日志优先用于定位。
- 未修改且已经稳定的接口和模块不重复检查。
