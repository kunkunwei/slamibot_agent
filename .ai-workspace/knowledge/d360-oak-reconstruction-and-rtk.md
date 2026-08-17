# D360 OAK 相机三维重建 + RTK 定位（板内盘点 2026-08-17）

## 1. OAK 相机（OAK-4P-New）× N —— 与雷达做 3D 空间重建
- 位置：`/home/jetson/SLAMIBOT_D360_Framework/src/oak-camera_driver`（oak-camera_driver，ROS1 Noetic）
- 型号：**OAK-4P-New**（Luxonis DepthAI；`idVendor=03e7`，udev 规则在 `80-movidius.rules`）
- 规格：**四路相机同步采集** + IMU（README 官方支持四路；用户记忆为"三个 OAK 相机"，实际数量以现场为准，待确认）
- 特点：硬件触发同步（`oak_hardware_trigger_ros.launch`）、IMU 固件可更新、支持 Docker 运行
- 当前状态：本次盘点时 `/dev/video*` 与 lsusb 均无 OAK 设备（相机未连接/未加载驱动）

## 2. 雷达 + 相机融合三维重建：lidar_add_rgb
- 位置：`/home/jetson/SLAMIBOT_D360_Framework/src/lidar_add_rgb`
- 功能：把 OAK 相机 RGB 融合到 Livox 点云上 → 彩色三维重建（点云上色）
- 配置：`config/mono.yaml`（单目）、`config/stereo.yaml`（立体）、`config/faster_lio.yaml`
- launcher：`lidar_add_rgb_mono.launch`、`gdb_lidar_add_rgb_mono.launch`
- 依赖：TBB 2018（thirdparty 内置）；核心 `src/lidar_add_rgb.cpp`
- 关联：`src/faster-lio`（重建/建图）、`src/device_service`（设备服务）

## 3. RTK 定位模块（差分 GPS）
- 确认：RTK 是**差分定位/GNSS 模块**（室外绝对定位用），用户 2026-08-17 确认
- 记录：`~/rtk_record/*.txt`、`~/b74_record/*.txt` 每秒一条 NMEA `$GNGGA`（GGA 句）
- 从记录看当前多为空字段（`0,00,卫星数0`）→ 室内/无卫星环境时无有效定位
- 与前端/rosbridge 的对接（SLAMIBotApp）：
  - `/rtk/gga`：std_msgs/String（NMEA GPGGA）
  - `/rtcm/data`：std_msgs/UInt8MultiArray（RTCM 差分改正数，供 RTK 解算）
- 相关：前端 ConfigModal 有 RTK 状态显示（已连接/未连接）、rosbridge 地址配置

## 4. SLAMIBOT_D360_Framework 整体（补充）
- 目录：`src/{device_service, faster-lio, lidar_add_rgb, livox_ros_driver2, oak-camera_driver}`
- 上层：`docker-compose.yml`、`Dockerfile`、`docker_build.sh`、`sync_deploy.sh`、`setup_env.bash`、`compile.bash`
- 其他：`ota_server`（OTA/设备服务）、`sbus`（遥控直连）、`webrtc`（控制链路）、`udev_rules`、`packages`、`docs`、`logs`