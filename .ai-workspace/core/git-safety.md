# Git 安全机制（Git Safety）

目标是让 AI 的任何修改都能**轻松、完整地撤回**。

## 改前（强制）
1. 任务开始前，在目标业务仓库执行 `git status` 并记录到任务条目（或日志）。
2. 检查是否有**用户未提交的修改**。若存在且与任务范围重叠：**停止并报告**，不得覆盖。
3. 确认当前分支、是否干净、是否落后/领先远端（`git status -sb`）。

## 改中（约束）
- 只能在任务 scope 内的路径修改（见 `change-policy.md`）。
- 建议为任务创建专用分支或安全检查点（分支名如 `ai/<task-id>-<简述>`）。
- 小步提交，每次提交信息写清楚“改了什么、为什么”。

## 改后（强制）
1. 展示 `git diff`（或 `git diff --stat` + 关键片段）。
2. 生成**变更摘要**：改了什么文件、为什么改、影响范围、如何回退。
3. 不得自动 `git push`（除非任务明确授权）。

## 禁止（未经人工授权，一律不得执行）
- `git reset --hard`
- `git clean -fd` / `git clean -fdx`
- 批量删除文件 / 目录
- `git checkout -f` / 强制检出 / 丢弃未提交修改
- 删除分支、重写历史（rebase -i、filter-branch、force push）
- `git stash drop`、`git restore .` 等丢弃性操作
- 任何“无法确定是否安全”的 Git 操作 → 停止并请求人工确认

## 回滚
- 单文件：`git checkout -- <file>`（或 `git restore <file>`），丢弃单个文件的 AI 改动。
- 全量：`git checkout -- .`（确认无用户未提交修改后）。
- 分支：切换/删除 `ai/*` 任务分支即可整体撤回。
- 本工作区：自身是 git 仓库，`git log` / `git diff HEAD` / `git checkout -- .` 可回退，或直接删除目录。

## 记录
- 每次任务把「git status（前）、git diff（后）、变更摘要、回滚方式」写进任务条目或 `tasks/`。
