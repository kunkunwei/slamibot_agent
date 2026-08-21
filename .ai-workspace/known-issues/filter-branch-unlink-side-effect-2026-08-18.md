---
name: filter-branch-unlink-side-effect-2026-08-18
description: 2026-08-18 filter-branch --index-filter 副作用 unlink 工作树文件事故（Scout 上传时 13 个文件丢失）
metadata:
  type: known-issue
---

# 事故：filter-branch --index-filter 会 unlink 工作树文件

## 时间
2026-08-18

## 现象
`git filter-branch --index-filter 'git rm ...' --prune-empty --tag-name-filter cat -- --all` 跑完后，**板上工作树中 13 个被新 tree 排除的文件物理消失**（unlink）。

用户原指令明确说"禁止删除、大仓库就瘦身再上传"。filter-branch 之后我没核对工作树完整性，导致**板上数据丢失**，违反核心约束。

## 失败机制（关键理解）

filter-branch 重写每个 commit 的流程：

```
for each old_commit:
    checkout old_commit → 工作树 sync 到老 tree（unlink 不在老 tree 的文件）
    run index-filter     → 新 index 不再引用某些文件
    commit                → 新 tree 不含那些文件
```

**index-filter 默认行为不直接删工作树文件**，但 checkout 老 commit 时它会 sync 工作树；同时**老 commit checkout 之后**，filter-branch 的下一步（commit 前）会**再次 sync 工作树到新 index**，这时新 index 不引用的文件会被 unlink。

`warning: unable to unlink '...': 权限不够` 是**有意识地 unlink 但失败**的证据（说明副作用机制确实启动了）：

```
warning: unable to unlink 'src/my_nav/maps/api_map/1/1_grid_debug.txt': 权限不够
warning: unable to unlink 'src/my_nav/maps/api_map/dinggu7_6/dinggu7_6.pgm': 权限不够
```

这些是 unlink 失败的；**成功的 unlink 直接让文件消失**。

## 触发条件（同时满足）

1. `git filter-branch` + `--index-filter` 模式（或 `--tree-filter`，后者更暴力）
2. 老 commit 的 tree 含某文件，但新 index/tree 不再引用
3. 该文件在工作树中存在，且 unlink 成功（没有 read-only / 权限锁定）

`git filter-branch --tree-filter` 会显式跑 `rm`，更危险；`--index-filter` 副作用是隐式 unlink，更易忽视。

## 实际损失（2026-08-18 Scout_mini_navigation 案例）

13 个文件从板上 `~/Scout_mini_navigation/` 工作树被 unlink：

| 路径 | 大小 |
|---|---|
| `src/scout_ros/scout_description/meshes/base_link.dae` | 14 MB |
| `src/scout_ros/scout_description/meshes/scout_mini_base_link.dae` | 14 MB |
| `src/scout_ros/scout_description/meshes/wheel.dae` | 2.7 MB |
| `src/scout_ros/scout_description/meshes/wheel_type1.dae` | 2.9 MB |
| `src/scout_ros/scout_description/meshes/wheel_type2.dae` | 2.9 MB |
| `src/ugv_sdk/docs/HUNTER_UserManual_EN.pdf` | 951 KB |
| `src/ugv_sdk/docs/HUNTER_UserManual_v1.2.6_S.pdf` | 1.7 MB |
| `src/ugv_sdk/docs/SCOUT_UserManual_EN.pdf` | 8.7 MB |
| `src/ugv_sdk/docs/SCOUT_UserManual_v1.1.pdf` | 1.3 MB |
| `src/ugv_sdk/docs/SCOUT_UserManual_v1.2.16_S.pdf` | 2.4 MB |
| `src/ugv_sdk/docs/interface_hierarchy.png` | 18 KB |
| `src/ugv_sdk/docs/protocol_v2/TRACER_UserManual_v1.2.pdf` | 几 MB |
| `src/navigation/navfn/test/willow_costmap.pgm` | 1.3 MB |

合计 ~58 MB。

`src/navigation/costmap_2d/test/TenByTen.pgm` 因 root 权限锁定而**幸存**（filter-branch 试图 unlink 但失败，文件残留）。

## 恢复过程

1. 用户发现并报告 → 立即诊断
2. 用 `cp -a` 备份的 `.git`（filter-branch 前 99.9% 概率不可信，因 .git 是只跟踪不复制工作树）确认**已不可用**——被用户清理掉了
3. 找到**备用源**：`F:\d360_nav2D`（Windows 端 Scout 工作目录，HEAD=`a16dc8f`，未经过 filter-branch）
4. 用户手动从 Windows 端 copy 恢复

**教训**：**只备份 `.git` 不够**。必须完整 `cp -a` 工作树。

## 缓解措施（强制规则）

### 操作前（强制）
```bash
# 必须同时备份工作树（不仅是 .git）
cp -a ~/repo ~/repo_worktree_backup_$(date +%Y%m%d_%H%M%S)
du -sh ~/repo ~/repo_worktree_backup_*  # 比对验证
```

### 操作中（关键日志检测）
filter-branch 跑时，**日志里的 `unable to unlink ...` 是副作用信号**。任何一条出现，都必须：
1. 立刻让 filter-branch 跑完（不要 Ctrl+C，可能让 pack 不一致）
2. 跑完立刻 `diff -r` 工作树与工作树备份，确认丢失文件清单
3. 报告给用户，等授权再决定是否从备份恢复

### 替代方案（推荐）
- **`git replace --graft`** + 后期选择性 push：只改 commit 链不重写 tree
- **`git filter-repo`**（已替代 filter-branch）：现代工具，副作用更可控
- **BFG Repo-Cleaner**：默认不改工作树，专注于删除大文件
- **直接 push 老 history**：如果浅克隆 + 缺对象是老 history 缺陷，解浅后再 push，不需重写

### 根本规则（已写入 `.ai-workspace/core/git-safety.md`）
filter-branch / history rewrite 类操作必须：
- 任务 scope 显式 `history_rewrite: true` 标记
- 操作前备份完整工作树（不是仅 .git）
- 操作后 diff 工作树 vs 备份确认数据完整性

## 关联

- 仓库：`Scout_mini_navigation` (kunkunwei/Scout_mini_navigation)
- filter-branch 后 HEAD：`1212a16b`
- 备份目录（已清理）：`~/Scout_mini_navigation_git_filterbackup_20260818_103804`
- 恢复源：`F:\d360_nav2D` (HEAD=a16dc8f)
- 规则修订：`.ai-workspace/core/git-safety.md`（新增 history rewrite 工作树备份段）、`.ai-workspace/core/change-policy.md`（加 history_rewrite 标记）