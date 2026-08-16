# 当前任务（current）

> 复杂任务模板见 `procedures/new-feature.md`。每任务必须含：id、目标、项目、技术栈、
> 当前阶段、允许修改范围(scope)、禁止修改范围(forbidden)、依赖、验证方法(validation)、回滚方案。

## 任务列表

<!-- 示例任务（仅用于验证工作流，不涉及真实业务修改） -->
- id: TASK-2026-08-16-000
  goal: 验证工作区工作流（示例，只读，不改业务代码）
  project: workspace
  technology: none
  lifecycle: CURRENT
  scope:
    - .ai-workspace/tasks/current.md   # 仅本文件
  forbidden:
    - 所有业务仓库
    - 系统环境
  dependencies: []
  validation:
    - 确认 Claude Code 能读取 CLAUDE.md 与 core 规则
  rollback: git checkout -- .ai-workspace/tasks/current.md
  status: done
  notes: 示例任务，用于 Step 5 验证工作流，无真实业务修改。
