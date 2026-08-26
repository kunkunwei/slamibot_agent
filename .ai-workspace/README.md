# SLAMIBot 本地 AI 开发工作区

面向机器人研发（导航 / 前端 / 后端 / 部署 / STM32）的**本地** AI 开发框架。目标是：简单、透明、
文件化、Git 可管理、可交接、可轻松回滚——而不是一个需要额外维护的复杂 Agent 平台。

- 所有知识、规范、任务状态、事实源都保存在**本机**这个目录里。
- Jetson 只作为远程编译 / 测试 / 运行目标，**不**在其上新增任何 Agent / RAG / 向量库 / AI 服务。
- 不依赖模型长期记忆，依赖**文件化事实源**。
- 复用你现有的 cc-switch（Claude / DeepSeek），**不**引入 LiteLLM 或额外模型网关。

## 目录结构

```
.ai-workspace/
├── README.md               ← 本文件
├── core/                   ← 全局工程规范（所有项目共享）
├── projects/               ← 每个业务仓库独立的上下文与约束
├── facts/                  ← 事实源（YAML，唯一可信来源）
├── knowledge/              ← 领域知识（架构/ROS1/ROS2/rosbridge/Jetson/Docker/机型）
├── interfaces/             ← 接口事实源（rosbridge/前端/后端/导航）
├── tasks/                  ← 任务状态（current / backlog / completed）
├── decisions/              ← 架构决策记录（ADR）
├── known-issues/           ← 历史踩坑记录
├── procedures/             ← 标准工作流程（开发/调试/验证/迁移）
└── agents/                 ← Agent 角色定义（Explorer / Implementer / Validator）
```

顶层 `CLAUDE.md` 是 Claude Code 的自动入口，通过 `@` 导入 core 规则，引用 facts/ 与 procedures/。

## 快速操作指南

### 1. 接入新的 Git 仓库
1. 编辑 `facts/repos.yaml`，新增一条仓库记录（填写 `remote_url`、`local_path`、`stack`、`status`）。
2. 在 `projects/` 下为该仓库建一个目录，复制一个 `project.md` 模板并填写技术栈与边界。
3. 若接口与其它模块相关，在 `interfaces/` 与 `facts/` 补充接口事实。
4. 状态未知的字段一律写 `UNKNOWN` / `NEEDS_CONFIRMATION`，不要猜。

### 2. 初始化一个项目
- 复制 `projects/<某个项目>/project.md` 作为模板，填写：`name`、`tech_stack`、`allowed_paths`、
  `protected_paths`、`protected_interfaces`、`protected_infrastructure`、`lifecycle`。

### 3. 定义项目规则
- 全局规范放 `core/`；项目级约束放 `projects/<项目>/project.md`；接口事实放 `facts/` 与 `interfaces/`。
- 项目级规则只能**更严**，不能放松全局规则。

### 4. 创建任务
- 在 `tasks/current.md` 顶部追加一条任务，使用 `procedures/` 里的任务模板（含 ID、目标、scope、forbidden、
  validation、rollback）。复杂任务必须写明技术栈与禁止范围。

### 5. 三个 Agent 角色怎么用
- **Explorer**（只读分析）：先让 Explorer 摸清架构、调用关系、Topic/TF、问题来源，产出「事实 + 假设 + 建议范围」。
- **Implementer**（受限修改）：只能在任务 scope 内改，改前 `git status`，改后 `git diff` + 摘要。
- **Validator**（只读验证）：检查 diff、编译、测试、日志、必要时远程 Jetson 验证；失败即停并报告，不无限自动修复。
- 详见 `.ai-workspace/agents/` 与 `core/agent-roles.md`。

### 6. 连接 Jetson
- 事实见 `facts/jetson_profile.yaml`。SSH 目标在 `~/.ssh/config`（当前 `116.148.216.66:30046`, user `root`）。
- 默认只做 `READ_ONLY`（查状态、查日志、rosnode/ros2 node、topic、docker ps/logs、git status/diff）。
- `BUILD` / `DEPLOY` 必须任务授权；`DANGEROUS`（删容器/网络、prune、rm、改系统配置、重启）永远人工确认。

### 7. 运行构建和验证
- 按 `procedures/<对应流程>.md` 执行；导航构建/真机验证走 `jetson-validation.md`。
- 所有验证结果必须落到文件（任务条目或 known-issues），不能只存在对话里。

### 8. 查看 diff
- Implementer 完成后必须展示 `git diff` 并附变更摘要；具体规范见 `core/git-safety.md`。

### 9. 撤回 AI 修改
- 业务仓库：用各自仓库的 `git status` / `git diff` / `git checkout -- <file>` / 分支回退（禁止 `--hard` 未经确认）。
- 本工作区：本身就是 git 仓库，`git log` / `git diff HEAD` / `git checkout -- .` 即可回退；或直接删除本目录。

### 10. 记录已知问题 / 架构决策
- 已知问题 → `known-issues/`，每个问题一个 `.md`。
- 架构决策 → `decisions/ADR-XXXX-<标题>.md`，格式见 `decisions/README.md`。

### 11. 项目交接给新成员
- 让其阅读本 README + 顶层 `CLAUDE.md` + `facts/repos.yaml` + `facts/robot_profile.yaml`。
- 完整流程见 `procedures/onboarding.md`。

### 12. 新增机器人型号
- 在 `facts/robot_profile.yaml` 增加新机型条目，在 `knowledge/robot-platforms/` 建文档，见 `procedures/add-new-robot.md`。

### 13. ROS1 与 ROS2 并存
- 严格按 `core/tech-stack-isolation.md` 与 `core/system-lifecycle.md` 处理，两套命令 / 工作区 / 事实源物理隔离。

### 14. 未来 ROS1 → ROS2 迁移
- 只能作为 `migration: true` 的独立专项任务，走 `procedures/ros1-to-ros2-migration.md`，需人工批准，绝不自动发生。

## 最重要的原则（速记）

本地保存、Jetson 不存 AI 状态；文件化事实源，不靠记忆；无 RAG/向量库/额外服务；ROS1/ROS2 严格隔离；
当前 ROS1 是默认稳定基线；ROS1→ROS2 是独立迁移项目；所有修改可审计可回滚；Agent 最小权限；
不因小任务擅自扩大范围；接口与关键参数显式记录；复杂任务有明确状态；验证优先于继续修改；
不确定即停止并报告，不猜测；不为“智能”增加不必要的基础设施。

## 已知问题索引补充（2026-08-21）
- APP/Web 地图、点云不显示的快速诊断：`.ai-workspace/known-issues/app-map-cloud-quick-triage-2026-08-21.md`
- 新会话遇到类似显示问题时，优先读取该记录，按“激活地图 → 资源文件 → 真实进程 → Topic 消息 → 既有启动接口”的顺序排查；禁止默认全局搜索。

- APP/Web 2D 栅格地图无消息的快速排查：`.ai-workspace/known-issues/app-2d-map-quick-triage-2026-08-24.md`
