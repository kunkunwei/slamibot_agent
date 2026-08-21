# D360 板内运行服务与容器详情（2026-08-19 只读复核）

## 运行中的容器
- **core**（image `slamibot_d360_firmware:latest`，自启动）：`project_control/core.launch`
  - `rosmaster`（11311，log 路径含雷达 MAC `00e09a2f15e6`）
  - `SystemMonitor`（system_monitor）
  - **`ntrip_rtk_service`**（NTRIP RTK 服务 —— RTK 差分数据源）
  - `LEDControl`（led_control）
  - **`rosbridge_websocket`**（core 内，无端口参数 → **默认 9090**）
  - `rosapi`
  - `camera_control_service`（camera_service）
  - `project_control_service`（device_basic）
  - `device_basic_service`（device_service）
  - 2026-08-19：9090 的 `rosbridge_library` 容器文件系统被应用三处 CBOR 兼容 live patch；未落到镜像，重启/重建 core 会丢失。独立探针已收到 `/map`，但 APP UI 仍未显示，详见 `known-issues/app-map-cbor-rosbridge-2026-08-19.md`。
- **firmware-sensors**（image 同，自启动）：`project_control/sensors.launch`
  - `livox_ros_driver2_node`（livox_lidar_publisher2，发布 /livox/lidar、/livox/imu）
  - **`oak_keyframe_stitcher`**（包 `ros1_oak_ffc_sync`，OAK 关键帧拼接 —— 相机关键帧与雷达/其它帧时空同步，三维重建关键环节）
- **ota_web**：设备设置/升级服务
- **scout-nav**（image `scout-nav:dual-rosbridge-20260819`）：当前运行
  - Nginx：80，`/rosbridge` 反代到 core 的 9090
  - FastAPI/nav_api：5000，内部连接 19090
  - `scout_nav_rosbridge`：19090，ROS 节点 `/scout_nav_rosbridge`
- **scout-nav-pre-dual-20260819**（image `scout-nav:latest`）：停止状态，作为部署前回滚容器保留
- **kn_nav_container**（image `kn_nav:v1`）：当前 Exited（自研 3D 未启动）

## 端口现状与职责

- **9090**：core 内客户端兼容 rosbridge，节点 `/rosbridge_websocket`；Android APP 与 WEB 使用。
- **19090**：scout-nav 内部 rosbridge，节点 `/scout_nav_rosbridge`；仅 FastAPI/nav_api 使用。
- **80**：Nginx WEB；同源 `/rosbridge` 实际上游为 `127.0.0.1:9090`。
- **5000**：FastAPI/nav_api；`/health` 的 `rosbridgeConnected` 只表示内部 19090。
- **11311**：共享 ROS Master。两套 rosbridge 访问同一 Topic/Service 空间。

2026-08-19 已通过唯一节点名解决两个 rosbridge 同名互踢；旧的“两个节点都叫
`/rosbridge_websocket`”仅是历史故障，不再是当前状态。

## 容器内路径
- 镜像把 SLAMIBOT_D360_Framework 装进 `/root/SLAMIBOT_D360_Framework/install`（core/firmware-sensors 里）

## 其它板内项目（补）
- **nav_frontend_redesign**：前端界面重构计划（git，master 干净），含 `HANDOFF.md`、`通信接口清单.md`、`前端界面重构计划.md`、`nav-web`、`start-all.sh`、`screenshots`、`backup`、`docs`
- **livox_bridge_ws**：ROS1/ROS2 livox 消息桥接工作区（`ros1_msgs_ws` + `ros2_msgs_ws` + `bridge_ws`，含 rebuild/reconfigure 日志）
- **unitree_sdk2_python**：宇树 SDK2 Python（官方）
- **kn_nav_backup**：自研 3D 备份（build/install/src）
- **docker_ws**：当前为空（印证文档"空目录挂载会遮蔽镜像同名目录"的坑）
- **sensors**：仅 `distinct` 子目录

## 运行时快照（2026-08-19 15:41）

- 运行容器：`core`、`firmware-sensors`、`scout-nav`、`ota_web`。
- 监听端口：**80、5000、9090、19090**；ROS Master 11311 由 core 提供。
- rosbridge 节点：`/rosbridge_websocket`、`/scout_nav_rosbridge` 同时存在。
- FastAPI 健康检查：`{"success":true,"service":"nav-api-fastapi","rosbridgeConnected":true}`。
- Nginx 最终配置：`location /rosbridge` → `proxy_pass http://127.0.0.1:9090`。

## 传感器 Topic 快照（2026-08-17，未在本次改端口任务中重新枚举）

- ROS 节点：camera_service / device_basic / device_service / led_control / livox_lidar_publisher2 /
  ntrip_rtk_service / oak_keyframe_stitcher / rosapi / rosbridge_websocket / rosout / system_monitor
- 三类关键 topic：
  - **相机三路**：`/SLB_CAM_A/compressed`、`/SLB_CAM_B/compressed`、`/SLB_CAM_C/compressed`
    （确认：实际 3 路 OAK 相机，A/B/C；与用户"三个 OAK 相机"记忆一致）
  - **RTK 五件套**：`/rtk/gga`、`/rtk/gnss`、`/rtk/raw`、`/rtk/rtcm`、`/rtk/satellites`（NTRIP RTK 服务发布）
  - **设备/系统**：`/battery` `/camera_temperature` `/cpu` `/cpu_temperature` `/memory` `/storage`
    `/project_duration` `/driver_status` `/clock` `/keyframe` `/slam_pose`
  - **底层对接**：`/stm32_cmd` `/stm32_serial`（与 STM32 下位机串口通信）、`/topic_frequencies`
    `/system_monitor_history` `/client_count` `/connected_clients`

## 镜像与其它
- 2026-08-19 当前 2D 导航镜像：`scout-nav:dual-rosbridge-20260819`；部署前容器
  `scout-nav-pre-dual-20260819` 保持停止状态供回滚。
- 2026-08-17 其它镜像快照：scout-nav:latest（18.2GB）/+rollback-20260813-1132；kn_nav:v1（8GB）；
  slamibot_d360_firmware:latest（4.96GB）；nav3d_d360:1.0（15.1GB，4个月前）；ros:foxy-ros1-bridge
- ota_web 容器进程：`./setting_server`（设备设置服务）
- STM32 固件：`~/slb_d360_stm32_2.0.4.bin`（29KB，2026-04-18）—— d360 分支产物
- sbus（遥控直连）：sbus_control.py / sbus_control_webrtc.py / sbusrecevie*.py
- ROS 服务：camera_service / device / led / livox / ntrip_rtk_service / oak_keyframe_stitcher 各 get_loggers/set_logger_level；
  另有 /current_ip、/ip_config、/get_version、/get_camera_status、/project_control、/project_list、/project_image、
  /project_delete（项目管理）、rosapi 系列（/rosapi/*）
