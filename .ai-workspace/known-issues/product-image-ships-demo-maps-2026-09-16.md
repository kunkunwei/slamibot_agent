# 已知问题：产品镜像自带演示地图，新设备首启会看到一堆地图名

发现时间：2026-09-16（新设备 192.168.31.164 首装后，用户在 APP 里看到很多地图名）
影响版本：`d360_nav2d:1.1 / 1.2 / 1.2.1`（以及更早的 scout-nav 镜像）

## 现象与真相

- **数据库不在镜像里**：镜像内只有 `/Scout_mini_navigation/install/share/nav_api/db/schema.sql`；`nav_api.db` 是首次启动时在宿主 `/var/lib/slamibot/scout-nav/db/nav_api.db` 生成（164 实测 81920 字节、时间＝安装时刻）。
- **地图文件在镜像里**：`install/share/my_nav/maps/api_map/` 带 21 个条目 / **82 个 .yaml**；首启时 `database.py:_bootstrap_installed_maps(seed_installed=True)` 会把它们写进新库并激活 `dinggu7_6`。
- 164 的 DB 里 16 条 Map 记录，`yamlFilePath` **全部指向镜像内 install share 路径** → 证实来源是镜像自带地图，而非拷库。
- 副作用：
  1. 混有开发/测试用名：`office_room_test123/3/4/5/6`、`test4/5/6`、`slam_map`、`1` —— 客户会误解为自己丢的图。
  2. 自带地图**只有 2D**（0 个 `.pcd`）→ 打开看不到 3D 点云。
- 用户数据是安全的：客户自己存的图在宿主 `db/maps` 下，不会进镜像。

## 处置（用户选择：从镜像剔除，干净交付）

目标版本：`d360_nav2d:1.2.2`

1. **镜像层（可立即做，秒级 overlay）**：
   ```dockerfile
   FROM registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d:1.2.1
   RUN rm -rf /Scout_mini_navigation/install/share/my_nav/maps/api_map/* \
       && mkdir -p /Scout_mini_navigation/install/share/my_nav/maps/api_map \
       && test -f /Scout_mini_navigation/install/share/my_nav/maps/pcd_to_map.py \
       && test -f /Scout_mini_navigation/install/share/my_nav/mapping_launch/fastlio_mapping.launch \
       && ls -A /Scout_mini_navigation/install/share/my_nav/maps/api_map | wc -l | grep -qx 0
   ```
   ⚠ 只删 `api_map/*`，**不要**动 `maps/` 下的脚本（`pcd_to_map.py`、`pcd_downsample.py`、`pcd_utils.py`）。
2. **源码层（需导航仓库副本，即 701 上线后）**：从 `src/my_nav/maps/api_map/` 删除自带地图（保留目录，必要时放 `.gitkeep`，避免 catkin `install(DIRECTORY)` 报错），并清理仓库里那份 committed `install/` 树；提交到 `codex/d360-nav2d-1.2-release-20260916`。这样后续全量构建也不会再带。
3. **已装设备清理**：164 切到 1.2.2 后，DB 里那 16 条指向镜像路径的记录会失效（文件已不在），需在**备份 DB 后**删除这些行：
   ```sql
   DELETE FROM Map WHERE yamlFilePath LIKE '/Scout_mini_navigation/install/%';
   ```
   备份：`cp -p /var/lib/slamibot/scout-nav/db/nav_api.db .../db/backups/nav_api.db.before-cleanmaps-<时间>`
4. 注意：清空后设备地图列表为空，属预期（客户先建图再导航；建图模式不依赖已有地图）。

## 阻断

**已解决（2026-09-16）**：镜像 `d360_nav2d:1.2.2` 已构建并推送 ACR（`sha256:3a282f35…`，远端 config digest 一致）；164 已切到 1.2.2，地图列表为 **0**，且无地图时建图仍可用（`/Odometry` 9.95Hz、`/scan` 10Hz 已验证）。源码层提交 `b2cfd1b`（`src/my_nav/maps/api_map/*` 全删 323 文件、加 `.gitkeep`），并推送 `release/d360-nav2d-v1.2.2` 与 `codex/d360-nav2d-1.2-release-20260916`；`scripts/install_2d_nav.sh` 也随该提交入库。

遗留：①701 自己的容器仍跑 1.2.1（其 DB 里是现场真实地图数据，不动）；②仓库 `src/my_nav/maps/` 顶层仍有约 **1005MB** 开发残留（`carto_map*.pgm/pbstream`、`test1-3`、`zhanhui_map*`、`map.pgm` 等），仅被 `my_nav_launch.launch:12` 的**注释**引用，是否清理待定。
