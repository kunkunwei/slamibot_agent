# SLAMIBot 本地 AI 开发工作区（Local AI Development Workspace）

本目录是 slamibot 机器人研发的「本地 AI 开发工作区」统一入口。所有 AI 开发规范、事实源、
任务状态、知识、流程与 Agent 角色定义都存放在 `.ai-workspace/`，由 Claude Code 原生加载。
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

- 当前任务：`.ai-workspace/tasks/current.md`
- 工作流程：`.ai-workspace/procedures/`
- Agent 角色：`.ai-workspace/agents/`
- 已知问题：`.ai-workspace/known-issues/`
- 架构决策：`.ai-workspace/decisions/`

## 快速开始

阅读 `.ai-workspace/README.md` 了解如何接入仓库、创建任务、连接 Jetson、撤回修改。
