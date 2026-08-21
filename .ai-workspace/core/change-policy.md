# 修改边界与变更策略（Change Policy）

每个项目必须明确四类范围（在 `projects/*/project.md` 中声明）：
- `allowed_paths`：任务可修改的文件/目录。
- `protected_paths`：默认禁止修改的路径。
- `protected_interfaces`：禁止改动的对外接口/协议。
- `protected_infrastructure`：禁止改动的基础设施。

## 默认禁止（除非任务明确授权）
- 系统环境（Ubuntu 包、环境变量、系统服务）
- Jetson OS 与系统配置
- Docker 基础设施（镜像、网络、compose 结构、daemon 配置）
- ROS 工作区结构（catkin_ws / colcon_ws 的目录约定）
- rosbridge 对外接口
- 数据库结构
- 前后端公共协议
- ROS1 / ROS2 版本迁移（必须 `migration: true` 专项任务）
- 改写 Git 历史（必须 `history_rewrite: true` 专项任务，且要完整备份工作树）
- 用户已有未提交代码

## 变更边界铁律
- **不擅自扩大范围**：小任务不顺手重构；不“既然改了就一起改”。
- **越界即停**：发现改动会触碰 protected 范围时，停止并报告，请求扩权或新任务。
- **迁移绝不隐式触发**：普通 ROS1 Bug 修复 / 功能开发不得触发 `migration`。

## 技术栈生命周期（详见 system-lifecycle.md）
- 默认所有导航优化 / Bug 修复 / 功能开发以 **CURRENT（ROS1 + Ubuntu 20.04）** 为目标。
- 仅当任务显式 `migration: true` 且写清 `from` / `to` 时才进入 MIGRATION / TARGET。

## History Rewrite 专项约束

任何修改 commit 历史的操作（`git filter-branch`、`git rebase -i`、`git replace --graft`、`git push -f`）必须显式标记为 **`history_rewrite: true`** 任务，并满足：

1. **任务文档**写明：`from`（修改前 HEAD）、`to`（修改后期望状态）、`reason`（为何必须改写）
2. **用户明确授权**（不是普通任务授权，而是专门授权"history rewrite 允许"）
3. **完整备份工作树**（不仅是 .git）—— `filter-branch --index-filter` 会 unlink 工作树中"不在新 tree 但在老 tree"的文件，详见 `known-issues/filter-branch-unlink-side-effect-2026-08-18.md`
4. **优先替代方案**：
   - 浅克隆 → `git fetch --unshallow <upstream>`（保留完整 history，不重写）
   - 大文件清理 → `git replace --graft` 或 BFG Repo-Cleaner（不动工作树）
   - 需要 reject 部分历史 → 优先 `git revert <commit>` 增量回退
5. **改后核对**：跑 `diff -r` 工作树 vs 备份，确认无 unlink 丢失；跑 `git fsck --full` 确认 .git 完整性
