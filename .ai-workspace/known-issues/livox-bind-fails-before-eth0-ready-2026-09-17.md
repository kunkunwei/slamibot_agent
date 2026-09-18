# 715 开机后雷达不出数据 → 相机/timeshare/5001/红灯 连锁失效（respawn 未触发）

- 设备：715 `jetson@192.168.31.164`（固件 `1.0.17`、导航 `d360_nav2d:1.2.3`）
- 发现时间：2026-09-17 14:10 CST（整机重启后约 6 分钟）
- 状态：**已恢复（运行时动作，未改任何代码/镜像）**
- **完整根因分析、依赖链、缺陷清单与修复备选 → `knowledge/d360-cold-boot-stability-analysis-2026-09-17.md`**（本文只记这一条具体缺陷）

## 现象（四条，同一根因）

1. 机身红灯闪烁
2. 5001 网页无雷达频率、无相机画面
3. `rostopic hz /SLB_CAM_A/compressed` → `no new messages`；`/keyframe` 无数据
4. `/topic_frequencies` = `{"/livox/lidar": 0.0, "/keyframe": 0.0}`，`/driver_status` = 8

## 根因链

`/livox/lidar` **有发布者但零消息** → `/dev/shm/timeshare` 未被创建 → `OakHardwareTrigger` 一直 `Waiting for timeshare` → 相机不出图 → 无 `/keyframe` → 5001 页面空 → `driver_status` 偏低 → 红灯闪。

livox 驱动日志（firmware-sensors 容器内）：

```
[info] Livox lidar logger disable. [parse_cfg_file.cpp] [Parse] [126]
bind failed
[error] Create detection socket failed. [device_manager.cpp] [CreateDetectionChannel] [275]
[error] Create detection channel failed. [device_manager.cpp] [CreateChannel] [242]
[error] Create channel failed. [device_manager.cpp] [Init] [169]
Failed to init livox lidar sdk.
[ERROR] Init lds lidar failed!
```

`/etc/slamibot/MID360_config.json` 把 `host_net_info` 的四个 `*_ip` 都写死为 `192.168.1.55`（eth0）。节点启动时该地址尚未由 NetworkManager 配到 eth0 上 → `bind()` 失败 → SDK 初始化失败。雷达本身正常：`ping 192.168.1.124` 0% 丢包、ARP `REACHABLE`。

## 为什么 `respawn="true" respawn_delay="3"` 没起作用

`respawn` 是**「进程退出才重启」**，不是健康检查。livox 节点 SDK 初始化失败后**只打日志、不退出**，进程一直活着并保持 ROS 注册（所以 `rosnode list` 里能看到 `/livox_lidar_publisher2`，但 Publications 无数据），roslaunch 没有任何可响应的事件。

证据（`/root/.ros/log/2d1a26b2-…/roslaunch-*.log`）：

```
78:[roslaunch][ERROR] 2026-09-17 14:16:43,933: [livox_lidar_publisher2-1] process has died
    [pid 50, exit code -15, cmd bash -c sleep 0.5; $0 $@ …/livox_ros_driver2_node …]
```

本次开机（14:03）到 14:16 之间，roslaunch 记录到的**唯一一次** `process has died` 就是人工 `pkill`（`exit code -15` = SIGTERM）。此前零次 → 从未触发 respawn。

`sensors.launch:29-33` 的 `launch-prefix="bash -c 'sleep 0.5; $0 $@'"` 只有 0.5 秒延迟，远小于 eth0 拿到 IP 所需时间。

## 恢复动作（本次实际执行）

```bash
docker exec firmware-sensors pkill -f livox_ros_driver2_node   # 强制退出 → 触发 respawn
```

3 秒后 roslaunch 重启节点并成功绑定。验证：

| 项 | 恢复后 |
|---|---|
| `/livox/lidar` | 10.000 Hz |
| `/dev/shm/timeshare` | 已创建（14:16） |
| `/SLB_CAM_A/compressed` | 9.936 Hz |
| `/keyframe` | 4.225 Hz |
| `/topic_frequencies` | `{"/livox/lidar": 10.0, "/keyframe": 4.0}` |
| `/driver_status` | 8 → 11 |
| 5001 | 200 |
| OAK 帧率统计 | 9.96 FPS |

## 待修（固件线，需重建镜像）

1. **初始化失败应退出**：`Init lds lidar failed!` 后应 `exit(1)`，让 `respawn` 能重试。
2. **启动顺序**：节点绑定 `192.168.1.55`，应在启动前等待该地址就绪（项目内已有同类写法：`OakHardwareTrigger` 等待 `/dev/shm/timeshare`），或依赖第 1 条的重试闭环。

## 关联

- 同一次重启还暴露：六麦阵列 `2208:0001`（`1-2.4.4.3`）USB 枚举失败 `error -71`，见 715 语音部署记录。
- timeshare 位于 **firmware-sensors 容器内** `/dev/shm`（容器重启不丢，整机重启清空）；工作区旧记录写的"在宿主 /dev/shm"不准确。
