# Scout Nav 全功能恢复 — Claude Code 执行交接

> 日期：2026-08-26  
> 适用栈：ROS1 Noetic + FastAPI + rosbridge + Android APP  
> 目标：在不删除现场证据、不直接回退旧容器的前提下，尽快恢复原来全部功能，并把当前容器内热修正式固化到代码和新镜像。

## 0. 给 Claude Code 的直接指令

1. 先读本文，再读 `.ai-workspace/facts/`、`.ai-workspace/tasks/context-checkpoint.md` 和目标仓库自己的 `AGENTS.md`。
2. 当前工作区事实源写明 Jetson 关机；聊天中的终端输出是历史现场。开始任何 SSH/Jetson 操作前，必须让用户明确确认设备已经开机。未确认前只做本地代码分析和方案准备。
3. Jetson 首轮只读确认，禁止根据本文旧 ID 直接操作容器或进程。
4. 目标不是回退容器，而是恢复并正式固化：建图、二维 `/map`、FAST-LIO 点云、导航、地图/PCD 保存、APP 完整 UI。
5. 不要重复做大范围泛化检查。按本文“执行顺序和验收门槛”推进，每一步记录命令、返回码和关键输出。

## 1. 当前生产现场（历史最后确认，执行前必须重新只读核对）

```text
container=scout-nav
id=b53206be42f2...
image=scout-nav:0cf1d78-installonly-lf-20260826
network=host
privileged=true
health.success=true
health.rosbridgeConnected=true
```

该容器是在旧生产容器基础上做的**可写层临时热修复**。原镜像本身没有固化下述修复；删除或重建该容器会丢失热修和容器内 `/tmp` 备份。

## 2. 已恢复并验证的运行链

### 基础感知

```text
/scout_base_node
/pointcloud_to_laserscan
/scan ≈ 10 Hz
```

### FAST-LIO

```text
/laserMapping
/fastlio_cloud_relay
/cloud_registered ≈ 10 Hz
```

### 二维地图

```text
ros-noetic-slam-gmapping 已安装到当前容器可写层
/slam_gmapping 已运行
/map publisher=/slam_gmapping
```

### ROS 时钟

```text
/use_sim_time=true
/clock publisher=/livox_lidar_publisher2
/clock ≈ 200 Hz
```

注意：`/map` 有 publisher 不等于 APP 已收到有效地图；必须再验证实际消息和 header/frame/timestamp。

## 3. 已确认根因与当前临时热修

### 根因 1：install-only 与源码绝对路径冲突

安装版 `launch_manager.py` 仍硬编码：

```text
/Scout_mini_navigation/src/my_nav/launch
/Scout_mini_navigation/src/my_nav/mapping_launch
/Scout_mini_navigation/src/FAST_LIO_gravity_align/PCD
```

install-only 容器最初没有这些源码目录，导致“launch 文件不存在”或模式启动失败。

当前容器临时创建了兼容链接：

```text
/Scout_mini_navigation/src/my_nav/launch
  -> /Scout_mini_navigation/install/share/my_nav/launch

/Scout_mini_navigation/src/my_nav/mapping_launch
  -> /Scout_mini_navigation/install/share/my_nav/mapping_launch
```

正式修复必须改代码使用 ROS package resolution、install/share 或明确的数据目录环境变量，不能长期依赖伪造 `src` 链接。

### 根因 2：FAST-LIO 安装规则漏装运行资源

`fast_lio_gravity_align` 的 CMake install 漏装 `launch/`、`config/`、`rviz_cfg/` 等运行资源，曾出现：

```text
No such file or directory:
/Scout_mini_navigation/install/share/fast_lio_gravity_align/launch/mapping_mid360.launch
```

当前容器已从宿主源码复制缺失资源到：

```text
/Scout_mini_navigation/install/share/fast_lio_gravity_align
```

容器内备份：

```text
/tmp/fast-lio-gravity-align-share-before-fix-20260826-141923
```

该备份随容器删除而丢失。正式修复应改 `src/FAST_LIO_gravity_align/CMakeLists.txt` 的 install 规则。

### 根因 3：镜像缺少 GMapping

当前容器可写层已安装：

```text
ros-noetic-slam-gmapping
/opt/ros/noetic/share/gmapping
/opt/ros/noetic/lib/gmapping/slam_gmapping
```

原镜像未固化。正式 Docker 构建必须加入 `ros-noetic-slam-gmapping`。

曾有安装验证脚本因 `set -u` 下引用未定义变量 `Package` 中断；这不是 gmapping 安装失败。宿主交互终端不要使用 `set -e` 或 `set -Eeuo pipefail`。

### 根因 4：FAST-LIO 建图 launch 原本只发 3D 点云，不发二维 `/map`

当前容器已创建：

```text
/Scout_mini_navigation/install/share/my_nav/mapping_launch/
  gmapping_with_fastlio_headless.launch
```

并修改：

```text
/Scout_mini_navigation/install/share/my_nav/mapping_launch/
  fastlio_mapping.launch
```

新组合包含：

```text
FAST-LIO mapping_mid360.launch
/cloud_registered -> /global_cloud_navigation relay
headless slam_gmapping
```

容器中还存在名称类似 `before-2d-*`、`before-headless-*` 的临时备份。Claude 必须先精确列出名字和内容；未经用户授权不得删除。

## 4. API 方法和状态陷阱

### 正确的一键高层接口

```http
GET /api/control/mode/mapping
GET /api/control/mode/navigation
```

高层接口会调用完整模式切换逻辑并更新 `current_mode`。

### 已发生的错误调用

```http
POST /api/control/mode/mapping
```

返回 404 的原因是 **HTTP 方法错误**，不是路由不存在。

```http
POST /api/launch/mapping/start
```

这是低级进程接口，只执行 `start_mapping()`，不会完整调用 `switch_to_mapping()`。因此出现过：

```json
{
  "current_mode": "idle",
  "mode_switching": false,
  "base_running": true,
  "mapping_running": true
}
```

该状态不表示建图进程失败，而表示低级接口启动进程后没有同步 `_current_mode`。执行现场恢复时优先调用正确的高层 GET 接口；正式代码中应评估并修正状态一致性，避免低级接口制造矛盾状态。

## 5. 当前必须处理的遗留 PCD publisher

历史最后确认 `/global_cloud_navigation` 同时有：

```text
/fastlio_cloud_relay
/pcd_map_publisher_159_53023
/pcd_map_publisher_166_1787707166696
/pcd_map_publisher_166_1787710416004
```

同时 API 显示：

```text
pcd_running=false
```

因此三个 `/pcd_map_publisher_*` 是后端已经失去句柄的遗留 ROS 节点。建图模式正常情况下应只保留 `/fastlio_cloud_relay`。

处理要求：

1. 先记录每个精确节点名、URI、PID、publisher topic 和启动时间（能取到则记录）。
2. 只精确停止上述已确认的遗留节点。
3. 禁止 `killall`、`pkill`、通配符杀进程或批量清 ROS 节点。
4. 停止后确认 `/global_cloud_navigation` 在建图模式只剩 `/fastlio_cloud_relay`。
5. 正式修复 PCD publisher 的持有、停止和模式切换生命周期，避免后端句柄丢失。

## 6. 我让用户创建/保留的容器与用途

**所有容器和镜像都是现场证据。不得删除、prune、覆盖或改名，除非用户再次明确授权。执行前必须重新 `docker inspect`，以下是历史最后状态。**

### 当前生产和失败切换证据

| 名称 | ID | 镜像 | 历史最后状态 | 用途/说明 |
|---|---|---|---|---|
| `scout-nav` | `b53206be42f2` | `scout-nav:0cf1d78-installonly-lf-20260826` | running | 当前生产；已做容器可写层热修 |
| `scout-nav-failed-installonly-20260826-135411` | `3df7d3d544ce` | `scout-nav:installonly-full-20260826-122020` | exited(0) | full install-only 切换失败后保留；缺 UI、地图、点云和建图功能 |
| `scout-nav-candidate-quick-20260826-134316` | `8a50c92a21cc` | 同上 | exited(0) | 隔离 roscore + `/health` 快速测试通过，但测试覆盖不足 |
| `scout-nav-candidate-installonly-20260826-133633` | `66e237647d8e` | 同上 | exited(1) | 首次候选；容器主机名无法回连自身，isolated roscore 失败 |

说明：快速候选只验证了 API 健康和 rosbridgeConnected，没有验证 UI bundle、模式切换、`/map`、点云、保存和导航，因此不能作为生产通过标准。

### 构建/打包辅助容器

这些容器主要用 `sleep` 保留镜像层或打包现场，不是生产服务：

```text
scout-nav-backend-pack-20260826-104708
  id=34e1227ad677  history=running
scout-nav-backend-pack-20260826-104512
  id=28270ca3228e  history=running
scout-nav-backend-pack-20260826-104912
  id=0534086a659c  history=exited(137)
scout-nav-pack-installonly-20260826-100900
  id=07593e87e5fb  history=running
scout-nav-pack-installonly-20260826-100534
  id=35199a2626b4  history=running
scout-nav-pack-installonly-20260826-101059
  id=9b96d1f99d05  history=exited(137)
scout-nav-failed-backend-20260826-104912
  id=e03aa32c9012  history=exited(3)
```

不要因为它们占用资源就擅自停止或删除。先向用户报告用途、资源占用和是否还需要，再申请授权。

### 其它历史回滚/失败证据

```text
scout-nav-fix-crlf-20260826-102353
scout-nav-failed-installonly-20260826-101059
scout-nav-failed-0cf1d78-20260826
scout-nav-pre-lf-20260826-102353
scout-nav-before-latest-20260824
scout-nav-pre-fix-20260824
scout-nav-broken-20260822
scout-nav-pr1-api-test
scout-nav-before-pr1-20260821-1125
```

旧容器常见持久数据挂载：

```text
/home/jetson/Scout_mini_navigation/src/my_nav/maps
  -> /Scout_mini_navigation/src/my_nav/maps

/home/jetson/Scout_mini_navigation/src/nav_api/db
  -> /Scout_mini_navigation/src/nav_api/db
```

任何新容器/候选必须核对地图和 DB 持久化路径，不能用 tmpfs 或镜像内目录替代生产数据。

## 7. 宿主和容器备份/临时文件

### 容器内关键备份

```text
/tmp/fast-lio-gravity-align-share-before-fix-20260826-141923
```

以及名称类似：

```text
before-2d-*
before-headless-*
```

先精确查找并记录，禁止删除。容器一旦删除这些也会丢失。

### 宿主 `/tmp` 候选测试记录

```text
/tmp/scout-nav-candidate-entry.sh
/tmp/scout-nav-candidate-name
/tmp/scout-nav-failed-candidate-name
/tmp/scout-nav-full-image-tag
/tmp/scout-nav-candidate-health.txt
```

它们是候选测试记录，不是正式部署资产，重启后可能消失。不要把正式恢复流程依赖在这些文件上。

### 用户提到的结果文件

用户说部分结果保存在 Jetson 当前目录的：

```text
fix_result.txt
```

开始执行后先只读确认其绝对路径、大小和内容，作为现场证据保留；不得覆盖。

## 8. 本地仓库历史最后状态（执行前重新核对）

### ROS1 导航/后端

```text
repo=F:\d360_nav2D
branch=codex/2026_8_25
head=25516ebf65fad1c404b9d1cdde0869a860ab367c
working_tree=clean
remote kunkunwei=git@github.com:kunkunwei/Scout_mini_navigation.git
remote origin=https://gitee.com/electech6/d360_nav2D.git
```

### Android APP

```text
repo=F:\SLAMIBotApp
branch=codex/native-compose-filament
head=9d3abebefa69a1197c7628dd7efbcd1bede57694
working_tree=clean
remote=git@github.com:electech6/SLAMIBotApp.git
```

APP mock 已声明：

```text
GET  /api/control/mode/mapping
GET  /api/control/mode/navigation
POST /api/launch/mapping/start
POST /api/launch/mapping/stop
```

注意区分 APP 原生 UI 与容器 Nginx 中 Web bundle。用户最初报告“APP 缺大量 UI”，必须确认实际缺失的是 Android 原生页面、WebView `/app/` bundle，还是构建时使用了错误前端产物。

## 9. Claude Code 执行顺序和验收门槛

### 阶段 A：恢复并验收当前运行态

前提：用户明确确认 Jetson 已开机。

1. 只读确认：当前 `scout-nav` 名称、ID、镜像、network、privileged、mounts、health；记录生产容器可写层变更。
2. 检查 `fix_result.txt` 和本文列出的容器/备份仍是否存在。
3. 调用正确高层接口：
   ```http
   GET /api/control/mode/mapping
   ```
4. 验收：
   ```text
   current_mode=mapping
   mode_switching=false
   base_running=true
   mapping_running=true
   navigation_running=false
   ```
5. 记录并精确停止三个失去句柄的 `/pcd_map_publisher_*`。
6. 验证 `/global_cloud_navigation` 只剩 `/fastlio_cloud_relay`，并有实际 PointCloud2 消息。
7. 验证 `/map` 不仅有 publisher，而且能在限定时间内收到 OccupancyGrid 消息；记录 frame_id、时间戳、宽高、分辨率。
8. 用户手动验收 APP：二维地图、实时点云、建图按钮/状态和原有 UI。Claude 不得用 `/health` 代替 UI 验收。

阶段 A 不通过，不进入构建或生产切换。

### 阶段 B：模式、保存、导航闭环

1. 通过现有高层模式流程停止建图，验证没有矛盾状态和遗留 launch 进程。
2. 验证地图保存、PCD 保存、激活地图、数据库记录和持久化宿主路径。
3. 验证保存产物不是只存在于容器可写层或 `/tmp`。
4. 调用：
   ```http
   GET /api/control/mode/navigation
   ```
5. 只验证启动链，不发送真实导航目标：
   ```text
   map_server
   amcl
   move_base
   正确的静态 PCD publisher
   /map publisher 与激活地图一致
   current_mode=navigation
   ```
6. 再切回建图，确认导航节点和静态 PCD publisher 被精确停止，实时点云 relay 恢复且无多 publisher 竞争。
7. 用户手动验收 APP 中模式切换、地图、点云、地图列表/激活和完整 UI。

阶段 B 不通过，不生成生产发布结论。

### 阶段 C：本地代码正式固化

只修改本次 scope；改前分别记录两个仓库 `git status --short --branch`，保留用户改动。

导航仓库至少检查/修改：

1. `Dockerfile`
   - 固化安装 `ros-noetic-slam-gmapping`。
2. `src/FAST_LIO_gravity_align/CMakeLists.txt`
   - install `launch/`、`config/`、`rviz_cfg/` 及所有运行必需资源。
3. `src/my_nav/CMakeLists.txt`
   - install `launch/`、`mapping_launch/`、`config/`、地图运行资源。
4. `src/nav_api/scripts/launch_manager.py`
   - 去除对 `/Scout_mini_navigation/src/...` 的硬编码运行依赖。
   - 优先使用 `rospack`/package path 或 install/share。
   - PCD/地图/DB 使用持久数据目录环境变量，不依赖源码树或镜像可写层。
   - 修复高层/低层接口造成的 `current_mode` 与进程状态不一致。
5. `src/my_nav/mapping_launch/fastlio_mapping.launch`
   - 正式组合 FAST-LIO、实时点云 relay、无 RViz GMapping。
6. PCD publisher 生命周期
   - 后端必须持有并精确停止它启动的节点/进程。
   - 进程句柄丢失后应能按节点身份安全回收，不产生重复 publisher。
7. 候选验收脚本
   - 不得只测 `/health`。
   - 必测模式切换、`/map` 实际消息、实时点云唯一 publisher、保存闭环、导航启动/停止、持久化 mounts。
8. APP/UI
   - 对比 Android 本地页面与镜像 `/usr/share/nginx/html/app/` 的 bundle 来源、构建 commit 和路由。
   - 找出“缺大量 UI”的具体产物差异，不用后端健康检查代替前端验收。

完成后分别提供任务范围 `git diff`；按工作区规则决定是否委派代码修改给 Claude Code MCP。普通修改可快速提交安全分支，但 BUILD、DEPLOY、生产切换必须再次得到明确授权。

## 10. 新候选的最低验收矩阵

| 项目 | 通过条件 |
|---|---|
| 容器 | host network、privileged、正确持久化 mounts、健康稳定 |
| API | `/health` 成功且 rosbridgeConnected=true |
| 基础感知 | base + pointcloud_to_laserscan 存在，`/scan` 有数据 |
| 建图状态 | 高层 GET 后 `current_mode=mapping` 且状态一致 |
| 3D 点云 | `/global_cloud_navigation` 建图时只有实时 relay，且有消息 |
| 2D 地图 | `/map` 有唯一正确 publisher 且能收到 OccupancyGrid |
| 保存 | 地图、PCD、DB 落在宿主持久化目录 |
| 导航 | map_server、AMCL、move_base、静态 PCD 正确启动 |
| 清理 | 模式切换后旧 launch/PCD publisher 无残留 |
| UI | 用户确认原有 UI、地图、点云、模式按钮均可用 |
| 回滚 | 旧生产容器和失败证据完整保留，回滚步骤明确 |

只有全部通过，才能报告候选可用于生产切换。

## 11. 严格禁止事项

未经用户新的明确授权，禁止：

- 删除、rename、覆盖本文列出的任何容器、镜像、地图、数据库、备份或 `fix_result.txt`。
- `docker prune`、镜像清理、容器批量清理。
- `docker restart`、Jetson reboot、系统服务重启。
- `killall`、`pkill`、通配符杀 ROS/系统进程。
- 在宿主交互终端设置 `set -e`、`set -Eeuo pipefail`；应显式保存每一步返回码，失败后仍保留终端和证据。
- 修改 Git 历史、`reset --hard`、`clean -fd`、force push。
- 混入 ROS2 命令、launch、参数、Topic/Service/Action 模型。
- 未完成候选全矩阵就 BUILD、DEPLOY 或切换生产。
- 用 `/health` 通过代替地图、点云、导航、保存和 UI 验收。

## 12. 建议给用户的阶段性报告格式

每完成一个阶段只报告：

```text
阶段：A/B/C
变更：精确文件/容器/节点
验证：命令 + 关键结果
未通过：明确故障点
保留：容器/镜像/备份
风险：是否仅存在于容器可写层
下一步：一个最短动作
授权需求：BUILD / DEPLOY / 生产切换 / 删除（如有）
```

不要让用户继续粘贴大段泛化日志；只请求一个最短、可判定的输出。
