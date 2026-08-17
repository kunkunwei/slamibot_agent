# D360 板内运行服务与容器详情（2026-08-17 只读盘点）

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
- **firmware-sensors**（image 同，自启动）：`project_control/sensors.launch`
  - `livox_ros_driver2_node`（livox_lidar_publisher2，发布 /livox/lidar、/livox/imu）
  - **`oak_keyframe_stitcher`**（包 `ros1_oak_ffc_sync`，OAK 关键帧拼接 —— 相机关键帧与雷达/其它帧时空同步，三维重建关键环节）
- **ota_web**：设备设置/升级服务
- **scout-nav**（image `scout-nav:latest`）：当前 Exited（2D 导航未启动）
- **kn_nav_container**（image `kn_nav:v1`）：当前 Exited（自研 3D 未启动）

## 端口现状（与文档对上的关键点）
- **9090**：core 内 rosbridge（无端口参数默认 9090）
- **19090**：scout-nav 内 rosbridge（`_port:=19090 _use_compression:=true`）
- 两个 rosbridge 共用节点名 `rosbridge_websocket` → 启动顺序/冲突是已知坑（文档错误排查 E 节）
- 其余：11311 ROS Master、5000 FastAPI、80 nginx、9000 外协3D Web

## 容器内路径
- 镜像把 SLAMIBOT_D360_Framework 装进 `/root/SLAMIBOT_D360_Framework/install`（core/firmware-sensors 里）

## 其它板内项目（补）
- **nav_frontend_redesign**：前端界面重构计划（git，master 干净），含 `HANDOFF.md`、`通信接口清单.md`、`前端界面重构计划.md`、`nav-web`、`start-all.sh`、`screenshots`、`backup`、`docs`
- **livox_bridge_ws**：ROS1/ROS2 livox 消息桥接工作区（`ros1_msgs_ws` + `ros2_msgs_ws` + `bridge_ws`，含 rebuild/reconfigure 日志）
- **unitree_sdk2_python**：宇树 SDK2 Python（官方）
- **kn_nav_backup**：自研 3D 备份（build/install/src）
- **docker_ws**：当前为空（印证文档"空目录挂载会遮蔽镜像同名目录"的坑）
- **sensors**：仅 `distinct` 子目录