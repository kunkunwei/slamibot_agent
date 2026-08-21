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

## APP 编译与安装边界（用户偏好，2026-08-21）
- APP 编译、APK 安装及真机部署由用户手动执行。
- Codex/Claude Code 默认只修改和检查 APP 源码，不主动运行 Gradle 编译、不执行 `adb install`，也不要求接管安装流程。
- 如用户在后续任务中明确要求代为编译或安装，再按当次授权执行；仅修改代码时报告源码变更和静态检查结果。

## Jetson 恢复操作快速路径（用户明确要求，2026-08-21）
- Jetson、Docker 容器或后端功能恢复时，**一切恢复版本以云端 Git 仓库为准**；优先使用已确认的远端分支/提交直接对比和恢复，不以现场散落文件、容器内临时改动或未经提交的备份作为主要版本源。
- 恢复前只做最小必要核对：远端仓库、目标提交、当前运行路径/挂载关系；禁止无目的地遍历大量文件、重复读取已确认内容或逐个猜测版本。
- 恢复操作走快速路径：按云端提交恢复任务 scope 内的最小文件集合，保留现场备份，完成一次语法/启动/API 验证即可；不覆盖整个容器，不改无关地图、数据库、导航和基础设施。
- Jetson 修改完成后必须立即执行：`git status` → `git diff` → 创建安全分支提交 → 推送云端 → 记录提交号；未推送不得声称恢复完成。
- 容器源码、挂载源码、`install` 产物和实际 Python 导入路径必须以云端提交为基线核对；如不一致，优先从云端重新同步对应 scope，禁止继续叠加临时热修复。
- 若云端提交不存在或远端不可达，立即报告阻塞原因；不得自行用现场临时版本替代云端基线。

## 备份最小化规则（用户明确要求，2026-08-21）
- 实际开发或恢复时，如果任务**不涉及修改、删除地图或其它尚未上传云端的运行数据**，禁止制作额外备份。
- 普通 Git 代码修改以 Git 分支、提交和云端推送作为回滚保障，不重复创建时间戳备份或复制整个目录。
- 只有涉及地图、数据库、未上传云端资源、非 Git 配置或其它不可由 Git 恢复的数据时，才允许并要求在变更前制作最小范围备份。
- 备份必须限定在任务 scope 内，禁止借备份之名复制或覆盖整个容器、工作区或无关数据。

## 通过后合并规则（用户明确要求，2026-08-21）
- 任务功能测试通过后，**仅针对 `kunkunwei` 名下的仓库**，将任务分支合并进对应仓库的 `main` 分支。
- 不在功能已验证通过后长期保留大量 `codex/*` 分支；合并完成后按仓库权限和 Git 安全规则清理已合并的临时分支。
- 合并前必须确认：任务 scope 内 `git diff` 已检查、关键验证通过、没有夹带用户已有改动、提交已推送远端。
- 非 `kunkunwei` 仓库不自动合并 `main`，除非用户另行明确授权。
- 合并不是测试通过的替代品：未验证通过不得合并；合并后仍需记录 merge commit 或目标 `main` 提交号。
