# Context Checkpoint — Scout Nav 全功能恢复交接

- 日期：2026-08-26
- 用户要求停止继续手工排查，改为由 Claude Code 执行。
- 完整交接：`.ai-workspace/procedures/scout-nav-full-recovery-claude-handoff-2026-08-26.md`
- 目标不是回退容器，而是恢复并固化建图、二维 `/map`、FAST-LIO 点云、导航、地图/PCD 保存及 APP 完整 UI。
- 历史当前生产：`scout-nav`，镜像 `scout-nav:0cf1d78-installonly-lf-20260826`，容器可写层有临时热修。
- 已验证：基础感知、`/scan`、FAST-LIO、`/cloud_registered`、GMapping、`/map` publisher、`/clock`。
- 临时热修：src→install 兼容链接；补 FAST-LIO install 资源；安装 gmapping；FAST-LIO launch include headless GMapping。
- 正确模式接口：`GET /api/control/mode/mapping`、`GET /api/control/mode/navigation`。
- `POST /api/control/mode/mapping` 为方法错误；低级 `/api/launch/mapping/start` 会造成 mode 与进程状态不一致。
- `/global_cloud_navigation` 历史存在 3 个失去后端句柄的 `pcd_map_publisher_*`；只能记录后精确停止，禁止批量杀进程。
- 所有候选、失败、打包和回滚容器均为证据，禁止删除/prune/覆盖。
- 关键容器内备份：`/tmp/fast-lio-gravity-align-share-before-fix-20260826-141923`；另查 `before-2d-*`、`before-headless-*`。
- ~~用户称 Jetson 当前目录有 `fix_result.txt`，只读保留，不得覆盖~~（已澄清：`fix_result.txt` 不存在，2026-08-26，不再搜索）。
- 本地导航仓库 `F:\d360_nav2D`、APP `F:\SLAMIBotApp` 的历史状态写在完整交接中，执行前重查 git status。
- 工作区事实源当前标记 Jetson 关机；用户确认开机前禁止 SSH。
- 下一步：Claude 按交接阶段 A 只读确认现场，再用高层 GET 恢复/验收建图；BUILD/DEPLOY/生产切换需另行授权。
- tests: SKIPPED（本任务仅编写交接文档）。

## 2026-08-26 进展更新（恢复执行后）

- **Plan C 已定案并执行**：建图模式移除 gmapping，只保留 FAST-LIO 3D 点云（`fastlio_mapping.launch` 已还原）。
  用户明确：建图中不展示实时 2D 地图（3D 雷达需转换）；已保存/转换好的 2D 地图要能在 APP 展示。
- **已验证闭环（2026-08-26，用户确认 APP 2D 地图显示）**：
  - 保存：`map2602` pcd(2.35GB)/pgm+yaml/display_pcd(14206点) 全部有效；PGM 为正常房间地图（40069 空闲 / 3383 占用）。
  - 降采样：走 `pcd_utils.voxel_downsample` 内联路径（`map_api.py:248`），**不依赖 `pcd_downsample.py`**（纠正此前假设）。
  - 激活：`POST /api/map/switch` → `my_nav_launch.launch` 的 `map_file` 更新为 map2602.yaml。
  - 显示：`GET /api/control/mode/navigation` → map_server/amcl/move_base 启动，`/map` 发布 map2602 栅格
    （frame=map, 0.05m/px, 213×204），APP `NativeOccupancyGridClient` 收到并显示。
- **关键事实**：FastAPI 监听 **5000** 端口（19090 是容器内 rosbridge，非 API）。
- **当前状态**：`scout-nav` 处于导航模式（map_server/amcl/move_base 运行）；**底盘(BOX)断开**，
  amcl/move_base 可能不健康，**导航闭环（Phase B）待底盘恢复**。
- 详细机制与证据：`known-issues/scout-nav-plan-c-saved-2d-map-display-2026-08-26.md`。
- 下一步：待用户确认 APP 2D 显示后，可切回建图模式继续建图；底盘恢复后验收 Phase B 导航闭环；
  Phase C 代码固化需另行授权。

## 2026-08-26 拍照功能热修部署（用户选「1」容器热修）

- **动作**：容器可写层热修，新增/补丁 4 个文件（`install/lib/python3/dist-packages/`）：
  1. `fastapi_service/capture.py`（新增，本地 288 行版）— 手动/到点拍照，队列 worker 持久化
  2. `fastapi_service/ros_client.py`（补相机缓存）— `_on_frame`/`start_camera_cache`/`get_latest_frame_snapshot` + import base64/time
  3. `fastapi_service/app.py`（挂载）— capture_router + `/captures` 静态 + `register_capture_tools` + lifespan `start_camera_cache()`
  4. `db/schema.sql`（追加 `Captures` 表，启动 `init_db()` 自动建表）
- **备份**：容器 `/tmp/capture-hotfix-backup-20260826/`（ros_client.py/app.py/schema.sql 原版）。
- **重启影响**：entrypoint `wait "$API_PID"` → kill uvicorn 后容器退出，已 `docker start scout-nav` 重新拉起；
  **当前导航模式已重置**（map_server/amcl/move_base 退出），需重新激活地图+切导航模式（底盘仍断开）。
- **验证通过**：`POST /api/capture/photo` 返回 success + id/fileName/url；文件落盘 `db/captures/`
  （220757B，JPEG 魔数 ffd8ff）；`GET /captures/<file>` HTTP 200；`GET /api/capture/list` 有记录；
  `/SLB_CAM_B/compressed` 10.1Hz；`/health` OK + rosbridgeConnected=true。
- **遗留**：`CAPTURE_DIR` 默认在容器可写层（`.../db/captures`），**非宿主持久化挂载**，重建容器丢；
  Phase C 固化时改环境变量指向持久路径。容器无 git（install 产物），回滚靠 `/tmp` 备份。
- 拍照数据落点：容器 `db/nav_api.db`（Captures 表）+ `db/captures/` 均在可写层，**需 Phase C 迁移持久化挂载**。

## 2026-08-26 底盘模式 API 对齐热修（用户确认「按清单热修」）

- **根因**：APP `BaseModeController.kt`（用户新改）期望新契约（`bases.SCOUT/GO2`、`policy`、`selectedBase/activeBase/detectedBase`、switch 支持 `auto|scout|go2`），容器 `base_mode.py` 是旧版（switch 仅 `none|scout|go2`，status 无探测字段）→ APP 解析全 null。
- **动作**：容器 `base_mode.py` 整文件替换为本地新版（973 行，含 `_probe_scout/_probe_go2/policy` 体系）；`ros_client.py` 补 `_latest_scout_status_at` 时间戳 + `get_scout_detection_snapshot()`（新版 `_probe_scout` 依赖）。
- **备份**：容器 `/tmp/base-mode-align-backup-20260826/`（base_mode.py 32806B + ros_client.py 15029B 旧版）。
- **重启**：kill uvicorn → entrypoint 重新拉起（容器未退出，ros_entrypoint 接管），**顺带使之前补丁的 teleop 1.5 运行时生效**。
- **验证通过**：`/health` OK + rosbridgeConnected=true；`/api/teleop_key/status` `maxLinear/maxAngular=1.5`；`/api/base_mode/status` 返回 `bases.SCOUT/GO2`（含 detected/candidateDetected/networkReachable/identityVerified/robotIp/interface/reason/lastSeen）+ `policy/selectedBase/activeBase/detectedBase/modeLabel/control/teleopEnabled/ready/reason`；`switch?mode=auto` → policy=AUTO；`mode=scout` → 底盘断开正确 fail-closed（ready=false, reason=SCOUT_HEARTBEAT_STALE）；`mode=go2` → GO2_DRIVER_NOT_CONFIGURED。
- **本地源码**：`F:\d360_nav2D\src\nav_api\fastapi_service\base_mode.py` 与容器已一致（973 行，commit 445ffd7 "feat: add safe chassis auto detection policy"）。
- **遗留**：底盘(BOX)仍断开，Scout `ready=false`（heartbeat stale）为预期；Phase C 固化时需将 base_mode/ros_client 热修并入正式部署。

## 2026-08-26 会话：底盘自动重连 / 时间同步 / 拍照 / 动作 404 四项处理

- **① 底盘自动重连（已完成+验证，commit 6b5582c）**：
  - 根因：容器旧版外部 Scout 采纳路径死锁（`/scout_base_node` 僵尸注册 → ready=false 但永不重启驱动）。
  - 修复：外部采纳路径心跳过期时 CAN 自检 → `rosnode kill` 清僵尸注册 → fall through 完整启动流程重新拉起；幂等分支共享 `_reconnect_can_locked()`。
  - 实测：驱动失联后 `switch?mode=scout` → 自动重启驱动 → `/scout_status` 恢复 50Hz。
  - 注意：**重启 uvicorn 会连带终止 managed roslaunch**（FastAPI shutdown 清理子进程）→ 底盘失联，需再次 switch 重连。
- **② 导航时间同步（已确认正常）**：`use_sim_time=true`、`/clock` 200Hz（ROS 虚拟时间 1776215178 ≈ 2026-04-15，比 wall 早 133 天 = by design，雷达驱动发布）、`/nav_multi/execute` 服务已注册（时间 gate 通过）、`/nav_multi/status=IDLE`。
- **③ APP 拍照（根因明确，阻塞 root 权限）**：OAK 相机 USB 在（`03e7:f63b`），宿主机 `oak_hardware_trigger_ros` 进程活（root 启动，`/root/SLAMIBOT_D360_Framework`，jetson 无 sudo 密码）但 **"总帧数：0 | 0.00 FPS"、`/driver_status=data:9`** → 相机 pipeline 初始化失败。话题配置确认未变（`/SLB_CAM_B/compressed`）。恢复需 root 重启 oak 驱动或检查相机；jetson 用户无法代为执行。
- **④ 动作栏 404（已修复）**：容器缺 `action.py` + models 请求模型 + app 挂载。热修：`docker cp action.py`、models.py 追加 NavigationAction*Request（5 类）、app.py import+include。验证 `/api/action/list` 返回 6 默认动作；`execute` 返回"暂未实现"（supported:false）。备份：容器 `/tmp/base-mode-align-backup-20260826/`（models_before_action.py、app_before_action.py）。
- **架构澄清**：宿主机视角的 `containerd-shim→nav-api-entrypoint→uvicorn→scout_base` 即 scout-nav 容器（同一进程双 PID namespace 视角），**无双 uvicorn / 无双 scout_base**。宿主机直跑 `project_control` roslaunch（roscore/livox/oak/camera_service）+ 容器跑导航/底盘/API。
- **安全**：teleop enabled=False、nav_multi IDLE、无活跃 cmd_vel → 小车完全静止。

## 2026-08-26 会话（晚）：容器自动自检自愈 + 5001 监控缺数据根因

- **容器重启自检自愈（任务完成，entrypoint 部署）**：
  - 新脚本 `nav-healthcheck.sh`（容器 `/usr/local/bin/nav-healthcheck.sh`）：自检 nav_multi 服务、rosbridge、底盘、相机、地图、时钟、SystemMonitor 遥测；容器内节点可自愈（pkill+重启），宿主机依赖（oak/livox/map/scan）只报告。
  - **关键修复**：master 重启后 `/use_sim_time` 参数丢失 → nav_multi 时间门控拒绝启动。自检在重启 nav_multi 前 `rosparam set /use_sim_time true`，实测 nav_multi 重启后成功注册。
  - entrypoint `/usr/local/bin/nav-api-entrypoint` 加自检守护：容器启动 20s（用户确认保持）后首次自检 + 每 60s 周期复查（后台子进程，**不阻塞启动**）。备份 `nav-api-entrypoint.orig-backup-20260826`，部署版 `nav-api-entrypoint.healthcheck-20260826`。
  - **容器启动顺序**已按 `core → firmware-sensors → scout-nav` 依赖在脚本注释标注。
- **5001 监控缺数据（温度/电池/雷达）+ 蓝灯闪烁 根因（已确诊+修复）**：
  - 根因链：STM32 主控 CH340 USB 串口（`/dev/ttyUSB1`→`/dev/ttySTM32`，USB 设备 `1-2.1.3`）硬件掉线（dmesg `failed to send/receive control message: -110`，复位后 `can't set config #1, error -110` 无法重新枚举），同 Hub `1-2.1` 的 RTK 串口（ttyUSB0）同时失联 → Hub/供电/线缆问题（软件无法恢复）→ SystemMonitor 打开串口 EIO 崩溃退出（core.launch 无 respawn）→ `/battery` `/cpu_temperature` `/cpu` `/memory` `/storage` `/topic_frequencies` 全无 → led_control 收不到电池 → 蓝灯闪烁。
  - 雷达实际正常（`/livox/lidar/pointcloud` 有数据），5001 页面雷达频率依赖 `/topic_frequencies`（SystemMonitor 发布）故显示空。
  - **修复**：用户物理重启 D360 后 STM32 USB 重新枚举成功 → SystemMonitor 恢复，`/battery`/`/cpu_temperature`（65.7°C）有数据，底盘 SCOUT ready、`/odom` 恢复，全链路自检 OK。
  - 5001 = SLAMIBOT 设备控制系统（连 9090 rosbridge，core 容器）；5000 = scout-nav FastAPI。
- **当前现场（2026-08-26 晚，重启后）**：相机 10Hz ✓、底盘 SCOUT ready + /odom ✓、/clock ✓、/battery ✓、nav_multi ✓、rosbridge ✓；/cmd_vel 无数据 = 车静止；/map /scan 需导航模式激活（预期）。
- **遗留**：STM32 USB Hub（1-2.1）掉线根因待观察（可能接触/供电，复发需物理检查或换 Hub）；App 底盘切换 timeout（5.8s 成功但 APP 超时）未深入；/rtk/gnss 无数据（RTK 未定位，待用户确认是否需连 NTRIP）。

## 2026-08-26 会话（深夜）：热修验证 + robot_map_pose 容器同步 + 导航规划失败诊断

- **热修验证（TASK-2026-08-26-001，只读）**：`/scan` 10Hz ✅、`/amcl_pose` 有消息 ✅、TF 链完整（map→odom(amcl)+odom→base_link+base_link→laser）✅、`/map` 563×217 有效 ✅、导航模式 + `/global_cloud_navigation` 仅 1 个 PCD publisher ✅。
- **膨胀参数 0.10 未生效为预期**：move_base 重启时加载旧 yaml（0.33/0.05）；0.10/12 是之后手动改的；需再重启 move_base 才生效。板上 src+install 的 tuned2 yaml 均已是 0.10/12（用户确认）。
- **根因：robot_map_pose 27 行转发只同步到宿主机，从未进入容器**：
  - 宿主机 `/home/jetson/Scout_mini_navigation/{src,install}/.../ros_client.py`：grep robot_map_pose=11（464 行）。
  - 容器内 `/Scout_mini_navigation/install/lib/python3/dist-packages/fastapi_service/ros_client.py`：grep=0（433 行，19:44 底盘热修版）。
  - 容器 Mounts 只挂 PCD/maps/db，install 目录非 bind mount → docker restart 不传播宿主机文件。
- **修复（方案 A，用户授权）**：docker cp 宿主机 install 版覆盖容器内 → grep=11、464 行、py_compile OK；`docker restart scout-nav`（用户执行）。
- **验证通过**：`/robot_map_pose` Publishers 出现 `/scout_nav_rosbridge` ✅；`/scan` 保持 10Hz ✅；APP 三角箭头能跟随真机移动 ✅、APP 可设置初始位姿 ✅（3D 箭头修复完成）。
- **新问题：导航任务不执行**：`/nav_multi/status` = FAILED，taskName=临时导航，move_base 状态码 4（ABORTED），text="Failed to find a valid plan. Even after executing recovery behaviors."（全局规划失败）。
  - TF/map/amcl_pose/costmap 均正常；当前无活跃 goal；`/move_base/GlobalPlanner/plan` 无新消息。
  - 待办：复现任务，抓目标点坐标与失败瞬间代价图，判断目标点不可达 / 起点在占据区。
- **日志采集器已部署**：`/home/jetson/nav_task_logger.sh`（daemon PID 47360 运行中，监听 /nav_multi/status）。
  - 每次任务自动采集到 `/home/jetson/nav_logs/task_<时间戳>/`（baseline/goal/status/feedback/amcl_pose/tf/rosout/final 快照）。
  - 本地源文件：`.ai-workspace/tmp/nav_task_logger.sh`（修复过 daemon 分支 local 报错）。
- **容器内备份**：`/tmp/rosclient-robot-map-pose-backup-20260826/ros_client.py`（覆盖前旧版）。
- **下一步**：用户在 APP 复现导航任务 → 读 nav_logs 分析 plan failed 根因；膨胀参数待重启 move_base 后验证 0.10；Phase C 固化待授权。

## 2026-08-26 深夜：APP 手动标点 Y 镜像 bug（实证 + 修复）

- **症状**：APP 3D 点云手动标点定位 → 箭头落在镜像位置（与按下点差别大）；导航后位姿不收敛、箭头一直错；自动重定位效果差。WEB 端手动定位正常。
- **排除**：`/global_cloud_navigation` frame_id=**map**（与 /map、/robot_map_pose 同帧，无帧不对齐）；后端链路正确（WEB 共用同一 /api/map/set_pose→/initialpose→AMCL，正常）。
- **根因（代码）**：APP `FilamentPointCloudView.kt` `groundIntersection` 在 filament 场景 Y=0 平面打射线后返回 `(filamentX, filamentZ)`，直接当 ROS (x,y) 发送。但渲染边界变换 `ROS_TO_FILAMENT_MATRIX` 是 `(x,y,z)->(x,z,-y)`，即 `filamentZ = -y_ros`——**缺一步逆变换，y 轴镜像**。拾取结果消费链：`handlePickTouch` → `onGroundPicked` → `NativeNavigationScreen.setInitialPose` → `/api/map/set_pose`。
- **实证（板上点云探针，10 样本全中）**：对每次 `/initialpose` 发出坐标与点云几何比对——9/9 次镜像点距 < 发出点距；7/9 镜像点几乎正好落在几何上（≤0.033m），发出点常空在 0.5~5m 外（见 `/home/jetson/initialpose_multi.log`、`probe_multi.py`、`pick_test_232657.txt`）。首样本：发出点 0 点、镜像 143 点 NEAR。
- **修复**：`F:\SLAMIBotApp` `groundIntersection` 返回值改为 `(filamentX, -filamentZ, 0f)`，注释同步更新。yaw 无需改（坐标修正后 `atan2(dy,dx)` 自动得正确 ROS yaw，与 WEB `atan2(world.y-press.y, world.x-press.x)` 一致）。
- **提交**：APP `a931ee2` `codex/native-compose-filament`（已推送 github electech6/SLAMIBotApp）。
- **为何标得准也不收敛**：镜像使发出的坐标翻到对称空旷处，AMCL 从错位起步、激光匹配不到、永不收敛；与标点精度无关。
- **下一步**：用户重建/重装 APP → 复测手动标点（箭头应落在按下处）+ 导航收敛。若仍不收敛再查 AMCL 参数（update_min_a/d）与地图匹配。板上遗留只读探针脚本可留证。
