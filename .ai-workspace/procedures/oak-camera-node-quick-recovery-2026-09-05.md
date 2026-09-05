# OAK 相机驱动节点单独恢复快速手册

更新时间：2026-09-05

适用：D360、ROS1 Noetic、`firmware-sensors` 容器、节点 `/oak_hardware_trigger_ros`。

现场状态：**2026-09-05 已按本手册单节点恢复，A/B/C 相机重新出图，PASS。**

> 本手册只处理“Livox 与共享时间健康，但 OAK 驱动进程退出”的场景。ROS 时间以 `/clock` 为权威来源；Jetson 系统墙钟和互联网 NTP不是本流程的同步源或恢复门槛。

## 1. 30 秒故障判定

宿主机先加载 ROS1：

```bash
source /opt/ros/noetic/setup.bash
rosparam get /use_sim_time
timeout 5 rostopic hz /clock
rostopic info /SLB_CAM_A/compressed
rosnode ping -c 1 /oak_hardware_trigger_ros
docker exec firmware-sensors bash -lc "pgrep -af 'oak_hardware_trigger_ros' || true"
```

可以进入“单节点恢复”的典型组合：

- `/use_sim_time=true`，`/clock` 持续更新；
- `/SLB_CAM_A/compressed`（通常连同 B/C）显示 `Publishers: None`；
- `rosnode ping` 报 `connection refused`，说明 ROS Master 可能只剩失效注册；
- 容器内 `pgrep` 无真实驱动进程；
- Livox Topic 与 `/dev/shm/timeshare` 仍持续更新。

补充确认 timeshare：

```bash
for i in $(seq 1 5); do
  date +%T.%3N
  docker exec firmware-sensors od -An -td8 -N16 /dev/shm/timeshare
  sleep 1
done
```

第二个 64 位整数持续变化即表示共享时间仍活跃。它属于传感器/ROS 时间链，**不要拿它和 Jetson 墙钟或互联网时间比较**。

以下情况不要直接启动：

- `pgrep` 已有真实 `oak_hardware_trigger_ros` 进程；
- `/clock` 不更新、Livox 无数据或 timeshare 不存在/冻结；
- 日志持续出现 `X_LINK_ERROR`、USB reset/disconnect；
- 项目正在采集且不允许相机短时中断。

## 2. 前台单节点恢复（推荐首次使用）

确认没有真实进程后执行：

```bash
docker exec -it firmware-sensors bash -lc '
source /opt/ros/noetic/setup.bash
source /root/SLAMIBOT_D360_Framework/install/setup.bash
exec rosrun ros1_oak_ffc_sync oak_hardware_trigger_ros \
  __name:=oak_hardware_trigger_ros \
  _fps:=20 \
  _frame_id_prefix:=oak_camera
'
```

保持该终端打开并观察启动日志。该进程是手动 `docker exec` 启动的，**不受原 roslaunch 管理**；关闭终端、按 Ctrl-C 或进程再次崩溃后不会自动拉起。

## 3. 后台单节点恢复（确认前台方案有效后）

```bash
docker exec -d firmware-sensors bash -lc '
source /opt/ros/noetic/setup.bash
source /root/SLAMIBOT_D360_Framework/install/setup.bash
exec rosrun ros1_oak_ffc_sync oak_hardware_trigger_ros \
  __name:=oak_hardware_trigger_ros \
  _fps:=20 \
  _frame_id_prefix:=oak_camera \
  > /tmp/oak_hardware_trigger_ros.manual.log 2>&1
'
```

查看后台日志：

```bash
docker exec firmware-sensors tail -n 100 /tmp/oak_hardware_trigger_ros.manual.log
```

后台方式同样不是永久修复：容器重启或进程退出后不会自动恢复。后续应单独评审在 `sensors.launch` 中增加受控 `respawn`，不能直接在现场改配置。

## 4. 恢复验收

```bash
rosnode ping -c 3 /oak_hardware_trigger_ros
docker exec firmware-sensors bash -lc "pgrep -af 'oak_hardware_trigger_ros'"
timeout 15 rostopic hz /SLB_CAM_A/compressed
timeout 15 rostopic hz /SLB_CAM_B/compressed
timeout 15 rostopic hz /SLB_CAM_C/compressed
timeout 15 rostopic hz /keyframe
```

通过标准：

- 节点可 ping，容器内只有一个真实驱动进程；
- A/B/C 都持续有频率和新帧；
- `/keyframe` 自动恢复。当前 `/oak_keyframe_stitcher` 存活时通常无需重启；
- APP/页面重新进入后可以看到实时图像。

## 5. 风险与升级条件

- **同名节点冲突**：真实进程存在时再次启动，同名注册可能关闭其中一个节点。
- **OAK/USB 争抢**：两个进程同时打开设备会触发设备占用、X-Link 异常或两边同时失败。
- **残留注册不是进程**：`connection refused` 时，`rosnode kill` 无法复活已经退出的驱动；清理注册也不等于启动进程。
- **X_LINK_ERROR**：若单次启动仍快速报错并退出，不要反复拉起。保存当前启动日志，升级到经授权的 `firmware-sensors` 容器恢复；若设备回落 Bootloader、USB reset/disconnect 持续出现，再升级为完整断电、USB3线缆/端口/供电检查。
- **上游异常**：若 `/clock`、Livox 或 timeshare 不健康，应先修复对应上游，不把问题归为 OAK 单节点故障。

## 6. 一行结论模板

```text
/clock=连续；timeshare=增长；OAK真实进程=无；rosnode ping=connection refused；A/B/C Publisher=None；单节点启动=PASS；A/B/C与keyframe=PASS；NTP=不作为判断条件。
```

关联文档：

- `.ai-workspace/procedures/customer-oak-camera-no-image-recovery-2026-08-25.md`
- `.ai-workspace/known-issues/ros1-docker-camera-topic-fake-dead-2026-08-25.md`
- `.ai-workspace/procedures/d360-704-oak-livox-calibration-diagnostic-manual-2026-09-02.md`
