# Git 安全机制（Git Safety）

目标是让 AI 的任何修改都能**轻松、完整地撤回**。

## 改前（强制）
1. 任务开始前，在目标业务仓库执行 `git status` 并记录到任务条目（或日志）。
2. 检查是否有**用户未提交的修改**。若存在且与任务范围重叠：**停止并报告**，不得覆盖。
3. 确认当前分支、是否干净、是否落后/领先远端（`git status -sb`）。

## 改中（约束）
- 只能在任务 scope 内的路径修改（见 `change-policy.md`）。
- 建议为任务创建专用分支或安全检查点（分支名如 `ai/<task-id>-<简述>`）。
- 小步提交，每次提交信息写清楚”改了什么、为什么”。
- 除 `git status` 外，必须建立目标文件级版本基线（mtime/size/SHA256）；写前乐观并发复核，任一外部变化或非预期 diff 即停止。
- 改后确认未回退其他 Agent 修改；共享文件的 base/latest/desired 三方合并、modified-on-disk 与锁协议遵循 `change-policy.md` 和 `../agents/team-orchestration.md`。

### History Rewrite（filter-branch / rebase -i / replace）前置检查
涉及改写历史（filter-branch、rebase -i、replace --graft、force-push 等）必须**全部满足**：

1. **任务 scope 显式标记** `history_rewrite: true`，且用户明说授权。
2. **备份完整工作树**（不仅是 .git，因为 filter-branch --index-filter 会在 checkout 阶段 **unlink 工作树文件**，详见 `known-issues/filter-branch-unlink-side-effect-2026-08-18.md`）：
   ```bash
   cp -a ~/repo ~/repo_worktree_backup_$(date +%Y%m%d_%H%M%S)
   du -sh ~/repo ~/repo_worktree_backup_*  # 验证备份大小
   ```
3. **观察日志**：`unable to unlink ...` 是副作用启动信号，必须跑完后 `diff -r` 工作树与备份比对丢失清单。
4. **撤回到原点的工具**：默认用 `git replace --graft`、BFG Repo-Cleaner 或解浅克隆（`git fetch --unshallow`），**这些都不动工作树**。filter-branch 是最后的备选。

## 改后（强制）
1. 展示 `git diff`（或 `git diff --stat` + 关键片段）。
2. 生成**变更摘要**：改了什么文件、为什么改、影响范围、如何回退。
3. 不得自动 `git push`（除非任务明确授权）。

## 禁止（未经人工授权，一律不得执行）
- `git reset --hard`
- `git clean -fd` / `git clean -fdx`
- 批量删除文件 / 目录
- `git checkout -f` / 强制检出 / 丢弃未提交修改
- 删除分支、重写历史（rebase -i、filter-branch、force push）— **filter-branch 副作用风险见下方**
- `git stash drop`、`git restore .` 等丢弃性操作
- 任何”无法确定是否安全”的 Git 操作 → 停止并请求人工确认

### filter-branch 副作用警告
`git filter-branch --index-filter` **默认会在每个 commit 重写时 unlink 工作树文件**（不在新 tree 但在老 tree 的文件）。这与 “禁止删除数据” 约束冲突。详见 `known-issues/filter-branch-unlink-side-effect-2026-08-18.md`。

**严格前置**：
1. 任务 scope 必须有 `history_rewrite: true`
2. **必须 `cp -a` 完整工作树**到非 .git 路径（仅 .git 备份无法恢复 unlink 掉的文件）
3. **优先替代方案**：`git fetch --unshallow` 解决浅克隆；`git replace --graft` 局部改写；BFG Repo-Cleaner 删大件——这些都不动工作树

## 回滚
- 单文件：`git checkout -- <file>`（或 `git restore <file>`），丢弃单个文件的 AI 改动。
- 全量：`git checkout -- .`（确认无用户未提交修改后）。
- 分支：切换/删除 `ai/*` 任务分支即可整体撤回。
- 本工作区：自身是 git 仓库，`git log` / `git diff HEAD` / `git checkout -- .` 可回退，或直接删除目录。
- **filter-branch 后工作树 unlink 文件的恢复**：不能从 .git 找回（被 unlink 的文件已不在任何 tree 中），只能从**工作树备份**或**未经过 filter-branch 的另一份相同仓库**（如 `F:\d360_nav2D`）取回。

## 记录
- 每次任务把「git status（前）、git diff（后）、变更摘要、回滚方式」写进任务条目或 `tasks/`。

## 用户快速上传授权（普通代码任务）

用户已明确偏好以 Git/GitHub 作为普通开发修改的版本留存，不为每个小改制作额外文件备份，并希望及时上传远端。本节在以下边界内构成常规授权：

- 改前仍执行快速 `git status -sb`，避免覆盖用户已有修改。
- 只暂存和提交当前任务 scope 内文件；不得把无关未提交修改带入提交。
- 普通 Git 仓库修改不创建时间戳目录/文件备份。
- 当前分支为明确的非保护开发分支且 upstream 正确时，可执行普通 `git push`。
- 当前分支是 `main` / `master` / release 等保护分支，或远端目标不明确时，不直接推送该分支；创建并推送 `codex/<task>` 安全分支，等待用户决定是否合并。
- 永不自动 force push、重写历史、删除远端分支或覆盖远端冲突。
- 历史改写、批量删除、非 Git 文件覆盖、系统/Jetson/Docker 基础设施变更仍不适用“无需备份”。
