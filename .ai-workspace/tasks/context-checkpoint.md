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
