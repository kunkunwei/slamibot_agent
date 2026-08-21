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

- Codex Luna：默认主协调，负责需求拆分、各 lane 快速扫描、Claude Code MCP 调用、联调定位和简短汇总。
- Codex Sol：当前后端/前端/导航至少两个 lane 需要共同解释同一端到端现象、存在共享接口/跨层因果链、protected 接口或高风险决策时必须自动介入；不等待 Luna 失败或用户点名，也不参与常规全量复查。
- Claude Code：按 lane 实施代码修改；最多同时运行 2 个任务，其余由 MCP 排队。
- 用户：手动运行、操作设备/界面、观察现象并提供复现步骤、抓包或日志。

## 复杂度门禁

开始实施或联调定位前先判断：

- `simple`：单 lane，或多个 lane 完全独立且没有共享接口/共同故障现象；由 Luna 协调。
- `complex-coupled`：至少两个 lane 相互依赖，或需要关联 API、WebSocket、rosbridge、ROS、容器、网络抓包/日志解释同一现象；必须先由 Luna 收集最小事实，再自动调用 Sol 给出跨层因果判断和 lane 归属。
- 用户明确要求 Sol 时，无条件按 `complex-coupled` 处理。

Sol 给出判断后直接进入各 lane 实施和用户联调，不增加重型阶段三审计。
## 流程

### 0. 仅在接口变化时确认契约

如果本次不修改 API、Topic、Service、消息字段、端口或状态码，直接跳过。稳定且已验证的区域不重复检查。

### 1. 按需并行实施

只启动实际涉及的 lane；不是每个任务都固定启动三组。

- Codex 给每个 lane 明确 `cwd`、允许路径、禁止路径和预期结果。
- 小任务优先 Luna 分析，Claude Code 单次实施。
- 默认不备份、不构建、不测试、不自动回环。
- Claude Code 返回：lane、状态、修改文件、摘要、`tests: SKIPPED (user fast mode)`、建议用户观察的现象。

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
