# 704 D360 NTP 后传感器与 LED 手动快速恢复

> **2026-09-05 更正声明（必须先读）**：原 NTP 前后恢复仅是历史相关性观测，不能定为因果。通用恢复应检查 `/use_sim_time`、`/clock` 连续性、timeshare/数据健康，不要求互联网 NTP。本文保留历史数据；其中规范性“必须 NTP yes”仅作为不再适用的历史实验步骤，禁止误执行。


更新时间：2026-09-02
适用：704 D360、ROS1 Noetic，仅 `core`、`firmware-sensors`、`ota_web`；无导航。

## 1. 当前结论与安全级别

firmware-sensors 早于 NTP 首次同步启动时，Livox 会出现约 2083Hz/96点包级消息。确认 `timedatectl show -p NTPSynchronized --value` 为 `yes` 后，经用户明确授权仅重启一次 firmware-sensors，同一 STM32 2.0.6 与同一 Livox 驱动恢复：lidar 10.011Hz、point_num 主值 19968/20064、IMU 199.863Hz、timeshare 持续增长、OAK 约10Hz、`/keyframe` 约3.67Hz。B 级重启和 LED 灯控均须逐次确认；本流程当前恢复动作已完成，不要重复执行。

## 2. 传感器快速恢复

### 0）确认项目已停

宿主机执行：
```bash
source /opt/ros/noetic/setup.bash
timeout 5 rostopic echo -n 1 /project_duration
rosnode list | grep -E 'laserMapping|lidar_add_rgb|record_node'
docker top core | grep -E 'rosbag|run_mapping_online|lidar_add_rgb' || true
# 只核对服务契约；停止项目时必须使用当前实际项目名，不要盲抄历史项目名
rosservice type /project_control
rosservice args /project_control
```
正常：`project_duration=0`，无 rosbag、laserMapping、lidar_add_rgb。异常：仍在采集或项目名不明。结论：不要重启传感器破坏现场，下一步先让 APP 停项目并确认项目名。

### 1）等待 NTP

宿主机执行：
```bash
timedatectl show -p NTPSynchronized --value
```
历史实验步骤（不再适用）：曾以 `yes` 作为继续条件；不得将其作为通用恢复门槛，也不要为此等待互联网 NTP。当前应检查 `/use_sim_time`、`/clock` 连续性及 timeshare/数据健康。

### 2）经确认重启传感器（B 级）

```bash
docker restart -t 20 firmware-sensors
```
正常：命令成功返回且容器重新运行。异常：超时、容器退出或反复重启。结论：不要连续重试，下一步保留容器状态和日志交人工处理。本次已执行一次并 PASS。

### 3）确认真实进程

```bash
docker ps --filter name=firmware-sensors
docker top firmware-sensors | grep -Ei 'livox|oak|stitcher'
source /opt/ros/noetic/setup.bash
rosnode ping -c 1 /livox_lidar_publisher2
rosnode ping -c 1 /oak_hardware_trigger_ros
rosnode ping -c 1 /oak_keyframe_stitcher
```
正常：容器稳定，真实 Livox/OAK 进程存在，节点 ping 成功。异常：仅 ROS 名称存在、无真实进程或 ping 失败。结论：这是残留注册/启动失败，不是数据健康；下一步保全后交人工，不直接再次重启。

### 4）30 秒健康验收

宿主机执行 IMU、timeshare 和 OAK：
```bash
source /opt/ros/noetic/setup.bash
timeout 30 rostopic hz /livox/imu
for i in $(seq 1 6); do date -Is; docker exec firmware-sensors sh -lc 'od -An -td8 -N16 /dev/shm/timeshare'; sleep 5; done
for t in /SLB_CAM_A/compressed /SLB_CAM_B/compressed /SLB_CAM_C/compressed /keyframe; do timeout 30 rostopic hz "$t"; done
```
容器内执行 Livox CustomMsg：
```bash
docker exec -i firmware-sensors bash -lc 'source /opt/ros/noetic/setup.bash; source /root/SLAMIBOT_D360_Framework/install/setup.bash; timeout 30 rostopic hz /livox/lidar; timeout 30 rostopic echo -n 5 /livox/lidar/point_num'
```
正常：lidar 约10Hz、point_num约20000、IMU约200Hz且无 `no new messages`、timeshare每次增长、OAK约10Hz、`/keyframe`约3.6–4Hz。异常：2083Hz/96点、停流、空包、timeshare冻结、OAK/keyframe无消息。结论：2083/96立即 FAIL，禁止开始采集；下一步保全证据并停止项目。本次已确认上述 PASS。

### 5）清理 APP 缓存并短测

完全关闭 APP/浏览器页面后重新打开，以清除 rosbridge 缓存。新建短测试项目后，静止 10 秒止损检查；通过后继续 60 秒漂移验收。正常：箭头/点云基本静止、`/slam_pose` 与 `/Odometry`约10Hz、无持续 `Too few`。异常：快速移动、频率稀疏或持续 Too few。结论：立即 stop_device，不重启硬顶；正常后才正式标定。

## 3. LED 恢复与回滚

### 3.1 只读预检

```bash
source /opt/ros/noetic/setup.bash
rosnode ping -c 1 /system_monitor
rosnode ping -c 1 /led_control
readlink -f /dev/ttySTM32
rostopic echo -n 1 /stm32_serial
```
正常：两个节点可 ping，别名指向 ttyUSB1，CH341 串口正常，GPRMC COG=206；`/stm32_cmd` 启动时无灯控消息。异常：串口指向 ttyUSB0、节点不可达或 COG 不符。结论：停止，不直接开串口绕过 SystemMonitor；下一步核对 RTK/STM32 设备。

源码闭环：`HARDWARE/WS2812/WS2812.c:88-93` 初始化主动全灭，`SYSTEM/iap/iap_rgb_control.c:7-8` 为 `active=0`；只有成功解析 `rgbcontrol` 才置 `active=1`。因此重启默认灭灯不等于 LED 硬件坏。

### 3.2 低风险灯控测试（B 级，每次确认）

用户已明确授权的一次测试命令：
```bash
source /opt/ros/noetic/setup.bash
rostopic pub -1 /stm32_cmd std_msgs/String "data: 'rgbcontrol:0:1:16:0:0:66'"
```
正常回执：
```text
rec rgbctl: rgbcontrol:0:1:16:0:0:66
[RGB] LED changed: Mode=0 Times=1 R=16 G=0 B=0 Version=1
```
再由现场确认低亮度红灯亮起。结论：该闭环支持 WS2812 硬件、STM32 解析、USB 串口和 ROS 链路正常；“开机没有下发 LED 初始化命令”仅为历史相关性解释，因果未确认。异常：无回执或物理不亮时停止，不重复乱发命令。

安全灭灯回滚（同样需确认）：
```bash
rostopic pub -1 /stm32_cmd std_msgs/String "data: 'rgbcontrol:0:1:0:0:0:66'"
```
不要使用 `times=0`，不要发未知命令；当前源码 checksum 验证被注释，末尾 `66` 只是兼容字段，未知命令可能触发 STM32 reset。不要直接打开串口绕过 SystemMonitor。

## 4. 未实施的永久修复方向

历史实验步骤（不再适用）：曾建议让 firmware-sensors 启动等待 `NTPSynchronized=yes`；不得将其作为通用恢复条件，也不要求互联网 NTP。永久修复应另行基于 `/use_sim_time`、`/clock` 连续性及 timeshare/数据健康设计。任何 systemd、compose、entrypoint、LEDControl/core 启动后主动发布产品默认灯色的代码/配置修改，均需另行授权；本流程不提供写文件命令。

## 5. 记录模板

记录 `/use_sim_time`、`/clock` 连续性、timeshare/数据健康、项目停止证据、容器/真实进程、lidar hz/point_num、IMU、OAK/keyframe、LED 回执及物理确认、异常与 stop 时间；NTP 值仅作历史相关性记录。密码和密钥不记录。
