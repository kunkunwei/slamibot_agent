# 分支清理记录 — 2026-09-16

## 结果
`kunkunwei/Scout_mini_navigation` 远端只保留 **master**（`1ad7809`），
master 由 `140f049` **快进**到 `1ad7809`（原 master 是快进祖先，无合并提交）。

## 清理前 8 个分支的提交点（可据此重建）
| 分支 | 提交 | 处理 |
|---|---|---|
| master | `140f049` → `1ad7809` | 保留（已快进） |
| codex/d360-nav2d-1.2-release-20260916 | `1ad7809` | 删除（= master） |
| release/d360-nav2d-v1.2.3 | `1ad7809` | 删除（= master） |
| release/d360-nav2d-v1.2.2 | `33a6cae` | 删除（master 的祖先后代，内容已在 master） |
| codex/d360-nav2d-1.1-release-20260916 | `3dad451` | 删除（`git cherry` 判定提交已全部在 master 线上） |
| feature/voice-mapping-no-confirm-20260909 | `0d4e9bf` | 删除（同上，提交已全部在 master 线上） |
| algo/teb-goal-tolerance-20260907 | `6dcb0ca` | 删除（基于旧 master 的旁支，见下"内容核对"） |
| codex/video-link-stream-20260904 | `f281b8e` | 删除（同上） |

## 两个旁支删除前的内容核对（确保没有独有工作被丢掉）
`git cherry -v 1ad7809 6dcb0ca` / `... f281b8e` 列出 3 个"非等价"提交，逐个核对：
1. `6dcb0ca tune(teb): relax goal tolerances to 0.25 and 0.30`
   → master 的 `src/my_nav/config/tuned2/teb_local_planner_params_tuned.yaml` 里
     `xy_goal_tolerance: 0.25` / `yaw_goal_tolerance: 0.30` **已在**（第 50/51 行）。等价，无损失。
2. `f281b8e fix(git): normalize navigation scripts to LF`
   → master 的 `docker-entrypoint.sh` 已是 LF（`file` 未报 CRLF）。等价，无损失。
3. `190ecc1 fix(docker): normalize product entrypoint line endings`
   → 其唯一实质产物是根目录 `.gitattributes`（`*.sh text eol=lf` / `Dockerfile* text eol=lf`），
     master 原本没有；已用 `git show 6dcb0ca:.gitattributes` 取回并提交为 `1ad7809`。已补齐。

结论：两个旁支除上述三项外无独有改动；三项均已核对或已补齐，故删除不丢工作。
701 上的本地克隆仍留有这些分支对象（如需重建：`git push origin <提交>:refs/heads/<分支名>`）。

## 连带更新
`D360装机流程.txt` §12.2 里 install_2d_nav.sh 的发布引用由 `release/d360-nav2d-v1.2.3` 改为 **master**。

## 遗留问题（本次发现，未修）
文档 §12.2 让装机人员 `curl https://raw.githubusercontent.com/kunkunwei/Scout_mini_navigation/master/...`
取脚本，但 **GitHub 仓库是私有的**（匿名 `api.github.com/repos/...` 与 `raw.../README.md` 均 404，
同网络下公开仓库 raw 返回 200），所以这一步在新设备上必然失败。

对比基础三容器那条（能用的）链路，它的分发渠道是**公开 Gitee + ACR**，与 GitHub 无关：
- 装机脚本：`https://gitee.com/electech6/d360_deploy/raw/master/setup_env.bash`（匿名 200，已验证）；
  该脚本第 5 步在设备上就地写 `/etc/slamibot/system/docker-compose.yml`（三容器定义）。
- 镜像：ACR `slamibot/*` 匿名可拉。在**无任何 docker 凭据**的 164 上实测
  `docker manifest inspect registry.cn-shanghai.aliyuncs.com/slamibot/{d360_nav2d:1.2.3,slamibot_d360_firmware:latest}` 均 OK。
  （注意：匿名直连 ACR `/v2/...` 会返回 401、token 端点的 `access` 为空，这是 ACR 的 API 行为，
   **不能**据此判断仓库私有；以 docker 自己的拉取流程为准。）

另外该脚本**不在导航镜像里**（`docker run ...:1.2.3 ls /Scout_mini_navigation` 只有 `install/`）。
可选修法：① 把脚本放到同一个公开 Gitee 仓库（与现有惯例一致，需有该仓库写权限）；
② 把脚本打进镜像（下个 tag，文档改成 `docker run --rm --entrypoint cat <镜像> <路径> > /tmp/install_2d_nav.sh`）；
③ 文档新增/强调 §12.3 手写 compose 路径——它不依赖任何下载，今天就能用。
