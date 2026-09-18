# 前端 / 后端 / 导航轻量团队协作

## 目标

以最少流程实现三条逻辑开发线并行：前端、FastAPI 后端、ROS1 导航。实现完成后不做重型 Codex 汇总审计，直接进入最小联调，以用户手动操作现象、抓包和关键日志作为主要反馈。

## 实际仓库边界

| lane | 工作目录 | 说明 |
|---|---|---|
| `frontend` | `F:\SLAMIBotApp` | 独立 Git 仓库 |
| `backend` | `F:\d360_nav2D\src\nav_api` | FastAPI，逻辑独立但与导航共用 Git 仓库 |
| `navigation` | `F:\d360_nav2D` | ROS1 CURRENT；任务必须排除 `src/nav_api`，除非接口任务明确授权 |

后端和导航同时写入时，必须满足其一：路径完全不重叠并按路径提交；或使用独立 Git worktree。不得让两个实施 Agent 修改同一文件。

## 角色

- Sol 主代理：负责理解用户需求、拆分 lane、判断共享接口和跨层因果、编写委派提示、联调定位及最终验收。
- Luna 执行子代理：默认使用 low，负责各 lane 边界明确的扫描、日志压缩、Git/diff 检查和独立并行检索；不自行解释模糊需求或裁决接口。
- Claude Code：按 lane 实施代码修改；最多同时运行 2 个任务，其余由 MCP 排队。MCP 可用性故障时由 Luna 按原 scope 单次接管。
- 用户：手动运行、操作设备/界面、观察现象并提供复现步骤、抓包或日志。

## 复杂度门禁

开始实施或联调定位前由 Sol 主代理判断：

- `simple`：单 lane，或多个 lane 完全独立且没有共享接口/共同故障现象；Sol 确定边界后，可由 Luna 执行扫描、检查和其它机械支线。
- `complex-coupled`：至少两个 lane 相互依赖，或需要关联 API、WebSocket、rosbridge、ROS、容器、网络抓包/日志解释同一现象；由 Sol 主代理建立跨层因果判断和 lane 归属。
- 只有额外的独立并行复杂分析确有价值或用户明确要求时，才创建 Sol 子代理；不得重复主代理已经承担的判断。

Sol 完成判断后直接进入各 lane 实施和用户联调，不增加重型阶段三审计。Claude Code MCP 失败只替换实施者，不改变复杂度门禁。
## 流程

### 0. 仅在接口变化时确认契约

如果本次不修改 API、Topic、Service、消息字段、端口或状态码，直接跳过。稳定且已验证的区域不重复检查。

### 1. 按需并行实施

只启动实际涉及的 lane；不是每个任务都固定启动三组。

- Sol 主代理给每个 lane 明确目标、最小必要事实、`cwd`、允许/禁止路径、权限模式、验证要求和返回格式。
- 1–2 次简单工具调用由 Sol 直接完成；超过约 3 次搜索/读取、长文件/长日志或多个独立扫描支线优先交给 Luna，避免中间输出进入 Sol 上下文。
- 普通业务代码优先由 Claude Code 单次实施；Luna 主要承担扫描、检查和 MCP 失败后的后备实施。
- MCP 工具未注册/未暴露、初始化或连接失败、Claude CLI 无法启动、认证/Provider/网络/限流不可用、无有效响应或超时时，自动创建或复用 Luna low 接管该 lane；Kimi Code 绑定 `custom/gpt-5.6-luna`。
- Luna 必须继承原 `prompt`、`cwd`、`mode`、`lane`、允许/禁止路径和测试策略；每个委派最多降级一次，不重试 Claude，不递归回退，也不得与仍在运行的 Claude 任务修改同一文件。
- 用户/权限策略拒绝、scope/cwd 或参数错误、危险操作确认、protected 边界和普通实现/测试失败不得触发降级。
- 默认不备份、不构建、不测试、不自动回环。
- Claude Code 正常完成时返回：lane、状态、修改文件、摘要、`tests: SKIPPED (user fast mode)`、建议用户观察的现象。
- Luna 完成时只返回结论、关键证据、修改摘要和验证；降级任务额外标记 `fallback: claude-code MCP -> gpt-5.6-luna (low)` 及原始失败类别。

### 2. 轻量收口并上传

Codex 只做必要动作：

1. 确认各 lane 没有修改同一文件。
2. 查看任务文件的 `git diff`，不重新审查稳定模块。
3. 按 lane 提交并推送开发分支；不 force push、不自动合并保护分支。
4. 不执行原“阶段三”的接口、端口、状态、全仓库、全规则重复核对。

### 3. 直接联调

实现完成后直接进入联调：

- 前端：浏览器/Android 网络请求、WebSocket 帧、页面现象。
- 后端：HTTP 请求/响应、FastAPI 日志、关键字段。
- 导航：rosbridge 数据、ROS Topic/Service/Action 与节点日志。
- 网络层：按问题选择 DevTools、WebSocket 抓帧、HTTP 抓包或 `tcpdump`；不无目的采集全量数据。

用户反馈优先使用以下格式：

```text
操作：
预期：
实际现象：
发生时间：
是否稳定复现：
抓包/日志文件：
补充截图或视频：
```

Codex 根据现象先判断故障属于 frontend/backend/navigation 哪一层，只退回对应 lane 修复一次；不让三个 Agent 同时盲改，也不自动进入无限修复回环。

## 共享路径写锁

- 写锁登记字段至少包括：`lock_id`、`task_id`、`path`（或目录前缀）、`owner`、`base_hash`、`acquired_at`、`status`（`active|blocked|released`）、`inherited_from`（如有）、`expires_at`（仅提示，如有）、`released_at` 和 `release_reason`；建议登记于 `current.md` 固定区域，但本规则不创建该区域。
- 只有 Sol 主代理或状态文件 owner 才能登记、继承和释放写锁；获取前检查路径冲突。目录前缀重叠即冲突，不能仅因文件名不同而并发写入。
- 未持有锁不得写共享路径；不得通过更换工具、模型或 Agent 绕过锁。Claude→Luna 降级必须原样继承锁，不能重新抢占或扩大范围。
- 冲突时等待或返回待合并片段；`expires_at` 仅用于提醒复核，超时、Agent崩溃或会话结束均不自动释放。完成、阻塞、取消或转交时由 owner 明确更新 `status`、`released_at`、`release_reason`，并在收口前检查锁已释放。
- `current.md`、`context-checkpoint.md`、`completed.md`、`facts/`、`rules/` 默认受共享保护；checkpoint 具体单一 owner/唯一合并入口见 `../core/context-compaction.md`，版本与三方合并见 `../core/change-policy.md` 和 `../core/git-safety.md`。

## 并发上限

- Codex subagent：最多 3 个分析 lane 并行。
- Claude Code：最多 2 个实施任务并行，由 MCP 队列限制。
- Jetson 上的构建、部署和真实运行串行执行，并继续需要相应授权。

## 完成标准

普通开发任务：

```text
目标文件已修改
+ diff 范围正确
+ 开发分支已推送
+ tests: SKIPPED (user fast mode)
+ 已给出需要用户手动观察的现象
```

联调任务只有在用户提供运行现象或抓包/日志证据后，才能标记为联调通过或失败。
