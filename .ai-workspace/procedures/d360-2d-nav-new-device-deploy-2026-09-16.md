# D360 新设备部署 2D 导航（scout-nav / d360_nav2d）

更新时间：2026-09-16
适用：D360 + Jetson + Ubuntu 20.04 + ROS1 Noetic；基础三容器已按《D360装机流程.txt》装好。
镜像口径：`registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d:1.2`（manifest `sha256:7c3f8e29…`）
（= 源码分支 `codex/d360-nav2d-1.2-release-20260916@3dad451`，2026-09-16 发布；与 701 现运行态一致，且修掉了 1.1 缺失建图资源的构建规则问题）

> 维护提示：镜像必须包含 `install/share/fast_lio_gravity_align/{launch,config,rviz_cfg}`，否则**建图模式无法启动**（`POST /api/launch/mapping/start` 返回"launch 进程启动后立即退出"）。这份资源靠 `src/FAST_LIO_gravity_align/CMakeLists.txt` 里的 `install(DIRECTORY launch config rviz_cfg ...)` 规则产出；`Dockerfile.product` 已加构建期 `RUN test -f …` 防呆，缺失会直接构建失败。改动构建规则后务必做**全量 `install/` 树比对**（`LC_ALL=C sort` + `comm`），不要只抽样比对。

## 0. 前置条件（缺一项就起不来或看不到画面）

- `core` 容器在跑 —— **ROS master(11311) 由 `core` 提供**（`rosmaster --core -p 11311`，compose 的 `core.launch` 拉起）。导航容器启动时要等这个 master。
- 传感器侧按《D360装机流程.txt》验收通过：`/livox/lidar` ~10Hz、`/livox/imu` ~200Hz、`/SLB_CAM_A/B/C/compressed` ~10Hz，且 `/dev/shm/timeshare` 的数值**持续变化**（只看文件存在不算健康）。
- 已登录 ACR（新设备必须做）：`docker login registry.cn-shanghai.aliyuncs.com`（公司阿里云账号）。
- 宿主数据目录：`sudo mkdir -p /var/lib/slamibot/scout-nav`（首次可为空）。

## 1. 部署（一条命令）

```bash
docker login registry.cn-shanghai.aliyuncs.com

docker run -d \
  --name scout-nav \
  --restart unless-stopped \
  --network host \
  --privileged \
  --shm-size 64m \
  -v /var/lib/slamibot/scout-nav:/var/lib/slamibot/scout-nav \
  registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d:1.2
```

说明：
- **不需要任何 `-e` 环境变量**：镜像默认数据根就是 `/var/lib/slamibot/scout-nav`（内含 `db/`、`fastlio/`、`maps/`）。
- entrypoint `/ros_entrypoint.sh` + cmd `/usr/local/bin/nav-api-entrypoint` 都由镜像自带，不要覆盖。
- host 网络，不需要 `-p`；80（WEB）、5000（API）、9090/19090（rosbridge）直接对外。
- 首次启动会自动建 `db/`、`fastlio/PCD/`、`maps/api_map/`，建库并**播种镜像自带的 21 套演示地图**（`dinggu7_1…6`、`carto_map`、`clear_map`、`office_room_test` 等），默认激活 `dinggu7_6`（可用 `NAV_API_DEFAULT_MAP` 覆盖）。

## 2. 启动顺序

`core` →（等 ROS master 就绪）→ `firmware-sensors` → `scout-nav`。
手动重启时也给 core 留 20–30 秒再起导航容器；导航容器对 master 有等待超时，超时后需要重启它。

## 3. 验收清单

```bash
docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}'            # scout-nav 应为 Up
docker inspect -f 'restart={{.RestartCount}} oom={{.State.OOMKilled}}' scout-nav
curl -s http://127.0.0.1:5000/health                              # rosbridgeConnected:true
curl -s http://127.0.0.1:5000/api/launch/status                   # current_mode=navigation / navigation_running=true
ss -lntp | grep -E ':(80|5000|9090|19090)\b'                      # 四个端口都在听
docker exec scout-nav bash -lc \
  'source /Scout_mini_navigation/install/setup.bash && timeout 6 rostopic hz /map /scan'
```

- 浏览器 `http://<设备IP>/app/` 应看到 2D 栅格图与点云，地图列表 21 套种子地图。
- APP 侧用 `ws://<设备IP>:9090`（rosbridge）+ `http://<设备IP>:5000`（API）。

## 4. 从旧设备迁移数据（可选）

```bash
# 旧设备
sudo tar -C /var/lib/slamibot -czf /tmp/scout-nav-data.tar.gz scout-nav
# 新设备（先停导航容器）
docker stop scout-nav
sudo rm -rf /var/lib/slamibot/scout-nav
sudo tar -C /var/lib/slamibot -xzf /tmp/scout-nav-data.tar.gz
docker start scout-nav
```

覆盖 `db/nav_api.db`、`db/captures/`、`db/tts_cache/`、`maps/api_map/`、`fastlio/PCD/`。
迁移后 `curl -s http://127.0.0.1:5000/api/map/list` 的地图数量应与旧设备一致（701 当前为 33）。

## 5. 可选：写进 compose（长期更可复现）

在 `/etc/slamibot/system/docker-compose.yml` 追加：

```yaml
  scout-nav:
    image: registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d:1.2
    container_name: scout-nav
    network_mode: host
    privileged: true
    shm_size: 64m
    restart: unless-stopped
    volumes:
      - /var/lib/slamibot/scout-nav:/var/lib/slamibot/scout-nav
    depends_on:
      - core
```

升级时改 tag 后 `docker compose up -d scout-nav`。注意 compose 只挂 `/etc/slamibot` 等宿主目录，**不挂框架源码**。

## 6. 已知坑（均已在 701 踩过）

- **timeshare 冻结时不要启动相机**：`/dev/shm/timeshare` 由 Livox 点云路径维护。它冻结时相机会发布**完全相同的 `header.stamp`**（硬同步失效），此时宁可让相机停着，先修雷达点云。
- `Can not get index` / `Storage point data failed` 来自 bag 存储路径（`enable_lidar_bag=true`，源码 `lds.cpp:109 StorageImuData()`），**点云正常时也会刷，是长期噪声**；不要据此判定雷达掉线。
- 真故障判据是 `/livox/lidar` **没有发布者**（`rosnode info /livox_lidar_publisher2` 的 Publications 里没有它），不是"有发布者但无消息"。
- `/dev/shm/timeshare` 在 **firmware-sensors 容器内**（不是宿主）：容器重启不丢，**整机重启清空**。它由雷达数据路径创建，**雷达不出数据就不会有 timeshare，相机随之不出图**。（2026-09-17 更正：旧记录写的"在宿主 /dev/shm"不准确。）
- **开机竞争（2026-09-17 已定位）**：livox 驱动绑定 `/etc/slamibot/MID360_config.json` 里的 `192.168.1.55`，而该地址由 NetworkManager 在开机约 40-46 秒才配上；驱动启动早于它就 `bind failed`、SDK 初始化失败，且**失败后不退出**（`respawn` 不触发）→ `/livox/lidar` 有发布者无数据 → timeshare 不创建 → 相机无图 → 5001 空、红灯闪。完整分析见 `knowledge/d360-cold-boot-stability-analysis-2026-09-17.md`。当前只能运行时恢复：`docker exec firmware-sensors pkill -f livox_ros_driver2_node`。
- OAK 相机驱动节点在容器里**没有 respawn**（2026-09-16 的决定，避免时间链异常时自动重播冻结时间戳）；掉线不会自愈，按 `procedures/oak-camera-node-quick-recovery-2026-09-05.md` 人工处理。livox 与 stitcher 有 respawn。
- 容器内框架文件（如 `install/share/project_control/launch/sensors.launch`）的改动只在**可写层**，容器重建即丢；要持久必须重打 `slamibot_d360_firmware` 镜像。
- 语音链路（`run_mic_sherpa` / `assistant_runtime` / `xf_chat_standalone`）**不在导航镜像里**，由宿主 crontab 拉起，属独立部署项 → 已固化为可选组件 **`d360_deploy/voice/install_voice_assistant.sh`**（opt-in，**必须在导航容器起来之后再装**，因为守护脚本门禁要 `5000/health` 与 `5011/health`）；讯飞凭据不入仓库，由客户按 `voice/CUSTOMER-XUNFEI-SETUP.md` 自配。
- 宿主 `/` 盘要留足空间：导航镜像 5.3GB，构建/缓存另算；701 当前 53G free（77% used）。

## 7. 升级与回滚

```bash
# 升级：停旧的、保留、起新的
docker stop scout-nav                      # 数据在宿主，不丢
docker run -d --name scout-nav-vX ... <新 tag>   # 验证通过后再改名/替换
# 回滚：停新的，起旧的
docker stop scout-nav-new && docker start scout-nav
```

host 网络下同一时间只能跑一个导航容器（端口冲突），不能新旧并行对外。

## 8. 与《D360装机流程.txt》的关系

装机流程负责：Docker/ROS、udev 串口、`/etc/slamibot/system/docker-compose.yml`（core/firmware-sensors/ota_web）、eth0=192.168.1.55、`/etc/slamibot/MID360_config.json` 雷达 IP、U 盘挂载、FRP。
本流程负责在此基础上加导航容器。两者叠加即为完整的一台可用 D360 2D 导航设备。
