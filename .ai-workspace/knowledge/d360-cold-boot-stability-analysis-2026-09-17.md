# D360 冷启动稳定性与"启动慢"根因分析（待修复）

- 建立时间：2026-09-17
- 设备：715 `jetson@192.168.31.164`（固件 `1.0.17`、导航 `d360_nav2d:1.2.3`）；701 `192.168.31.135` 作对照
- 状态：**分析完成 / 未做任何修复**（用户要求先不动源码）
- 触发场景：整机断电重启后，红灯闪烁、5001 页面无雷达频率与相机画面、"启动很慢很不稳定"
- 关联：
  - 具体缺陷 → `known-issues/livox-bind-fails-before-eth0-ready-2026-09-17.md`
  - 测试方法 → `procedures/boot-stability-timeline-test-2026-09-17.md`
  - 探针脚本 → `tmp/boot_timeline_probe.sh`

---

## 0. 结论摘要（TL;DR）

1. **操作系统不慢**：`kernel 10.155s + userspace 7.052s = 17.2s`，docker 守护在 17.1s 就绪。
2. **"慢"来自一条串行依赖链**，每环之间没有等待、没有超时、没有重试：`eth0 静态 IP → livox 绑定 → 连上雷达 → 出 IMU/点云 → /clock 有数据 → timeshare → 相机 → /keyframe → nav_multi 拿到有效时钟 → 导航可用`。
3. **`/clock` 是整条链的咽喉**：唯一发布者是 livox 驱动，且**懒初始化在 `Lddc::PublishImuData()`**（`lddc.cpp:668-700`），时间戳取自 IMU 包。而 `/use_sim_time=true`，订阅者含相机、拼接、`nav_multi`、两个 rosbridge。**雷达一连不上，`/clock` 连发布者都不存在，所有节点时间冻结在 0，下游无限期停滞。**
4. **"不稳定"来自三个彼此独立、时间尺度相差三个数量级的启动过程在赛跑**：Jetson 网络（秒级）、Jetson 容器（十秒级）、**BOX 内六麦模块自己的一台嵌入式 Linux（分钟级）**。
5. **无保电 RTC** 导致一次开机内墙钟跳变 4 次（含一次 **+12 分 39 秒**前跳），使所有墙钟日志无法用于排序 —— 这是排查困难的主要人为障碍。
6. **失败不退出**：livox 节点 SDK 初始化失败后只打日志、继续 `while(ros::ok())` 空转，`respawn="true"` 永远不触发（厂商原始逻辑，非本项目引入）。

---

## 1. 一次冷启动的真实时序（单调时钟）

设备无保电 RTC，`docker inspect` 的 `1970-01-01T00:00:41` 即"开机后 41 秒"。

| t (秒) | 事件 | 证据来源 |
|---|---|---|
| 0 | 上电；`tegra_rtc: setting system clock to 1970-01-01T00:00:28 UTC` | 裸 `dmesg` |
| ~2.2 | `systemd-timesyncd` 启动 | `systemd-analyze critical-chain` |
| ~7-9 | USB 根 hub、OAK（先以 `Luxonis Bootloader` `03e7:f63c` 出现）、EC20 `2c7c:0125`、各级 hub | `dmesg` |
| 13.2 | cron `@reboot` 触发（本次为语音 supervisor） | `journalctl -b -o short-monotonic` |
| **16.1 / 17.1** | `docker.service` 启动 / `Daemon has completed initialization` | journal |
| 34.1 → 61.3 | BOX 侧 hub 链（`1-2.4.4.x`）枚举；**六麦口反复失败**：`device descriptor read/64, error -110` → `attempt power cycle` → `not accepting address 18/19, error -71` → `usb 1-2.4.4-port3: unable to enumerate USB device` | `dmesg` |
| **41.7** | 四个容器起来（core / firmware-sensors / ota_web / scout-nav） | `docker inspect .State.StartedAt` |
| **~43** | NTP 首次同步 → 墙钟 **前跳 12 分 39 秒** | journal |
| **~46** | livox 节点启动 → **`bind failed`** → `Failed to init livox lidar sdk.` → `Init lds lidar failed!` | firmware-sensors 容器内节点日志 |
| 61.8 | CH340 挂上（`ttyUSB3` / `ttyUSB4`） | `dmesg` |
| **1085.9 / 1096.9 / 1098.2** | **六麦模块三段式启动完成**（见 §3） | `dmesg` |
| 运行期 | 人工 `pkill -f livox_ros_driver2_node` → 3 秒后 respawn → 绑定成功 → 全链恢复 | roslaunch 日志 `exit code -15` |

对照（701，同一固件线）：容器在 **53.3s** 起来（715 是 41.7s），同样 `tegra_rtc ... 1970-01-01T00:00:24`（无 RTC）。

### 取证命令（可复现）

```bash
# 系统启动耗时
systemd-analyze ; systemd-analyze blame | head -20 ; systemd-analyze critical-chain

# 容器启动时刻（无 RTC 时该值即"开机后秒数"）
docker inspect core firmware-sensors ota_web scout-nav \
  --format '{{.Name}} Started={{.State.StartedAt}} Finished={{.State.FinishedAt}} Restart={{.RestartCount}}'

# 时序（必须单调时钟；dmesg 不要加 -T）
sudo journalctl -b -o short-monotonic --no-pager
sudo dmesg | grep -E 'usb 1-2\.4\.4|new .*USB device|unable to enumerate|not accepting'

# /clock 的发布者与订阅者（在导航容器内）
docker exec scout-nav bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; rostopic info /clock; rosparam get /use_sim_time'

# 实测启动耗时
cat /proc/uptime ; date ; uptime -s
```

---

## 2. 依赖链（顺序即判据）

```
上电
 → 内核/系统（17.2s）
 → docker 守护就绪（17.1s）
 → 四容器运行（41.7s / 701 为 53.3s）
 → eth0 拿到雷达网静态 IP 192.168.1.55（NetworkManager，~40-46s）   ← 与下一环竞争
 → livox 节点启动（~46s）并绑定该 IP → 连上雷达 192.168.1.124
 → 雷达出 IMU/点云 → /livox/lidar 有数据
 → /clock 有数据流（懒初始化，唯一发布者 livox）                     ← 咽喉
 → timeshare 创建 → 相机出图 → /keyframe
 → nav_multi 拿到有效时钟 → 导航可用
 → 5001 状态页完整 / driver_status=15 / LED 正常
 → 六麦模块自身启动完成 → 声卡可用 → run_mic → WAIT_WAKE            ← 独立变量
```

**每一环都没有超时与重试**，因此任何一环断掉，表现都是"卡死/很慢"，而非报错。

---

## 3. 三个独立启动过程在赛跑

| 过程 | 时间尺度 | 715 实测 | 备注 |
|---|---|---|---|
| Jetson 网络（eth0 静态 IP） | 秒级 | ~40-46s | NetworkManager `Wired connection 1`，autoconnect yes |
| Jetson 容器 + ROS 栈 | 十秒级 | 容器 41.7s，livox 节点 ~46s | livox 绑定时 IP 尚未就位 → `bind failed` |
| **BOX 内六麦模块（独立嵌入式 Linux）** | **分钟级** | **1085.9 → 1098.2s** | Allwinner Tina 平台，三段式枚举 |

六麦模块的三段式启动（dmesg 原文）：

```
[1085.944653] usb 1-2.4.4.3: new high-speed USB device number 21
[1086.146782] usb 1-2.4.4.3: New USB device found, idVendor=1f3a, idProduct=efe8, bcdDevice=ff.ff
[1088.948994] usb 1-2.4.4.3: USB disconnect, device number 21
[1096.964560] usb 1-2.4.4.3: new high-speed USB device number 22
[1097.168671] usb 1-2.4.4.3: New USB device found, idVendor=18d1, idProduct=d002   (Product: Tina ADB)
[1097.652997] usb 1-2.4.4.3: USB disconnect, device number 22
[1097.984565] usb 1-2.4.4.3: new high-speed USB device number 23
[1098.186633] usb 1-2.4.4.3: config 1 interface 1 altsetting 1 has an invalid endpoint with address 0x0, skipping
[1098.200141] usb 1-2.4.4.3: New USB device found, idVendor=2208, idProduct=0001   (ListenGo Circular 6-Microphone)
[1098.267404] cdc_acm 1-2.4.4.3:1.3: ttyACM0: USB ACM device
```

- `1f3a` = Allwinner 引导模式；`18d1:d002` = Allwinner Tina Linux（ADB 模式）；`2208:0001` = 最终应用固件。
- **Jetson 在 34-61 秒枚举该口时，撞上的是模块自己的启动过程** → `-110` / `-71` / `unable to enumerate` 与 Jetson 快慢无关。
- 本次模块到 **18.3 分钟**才可用；期间无人插拔。恢复后 supervisor 自动拉起 `run_mic`（fail-closed + 等待设计生效）。
- 待查：模块为何要到 1085s 才开始启动（是否有自身看门狗、供电时序、或前序 `attempt power cycle` 的影响）。

---

## 4. 时钟域问题（排查的人为障碍）

设备无保电 RTC，一次开机内墙钟跳变 4 次：

| 阶段 | 来源 | 715 实测值 |
|---|---|---|
| 内核早期 | 内核默认值 | `6月 18 04:29:39` |
| RTC 设定 | `tegra_rtc`（无电池） | `1970-01-01T00:00:28 UTC` |
| timesyncd 恢复 | `/var/lib/systemd/timesync/clock` | `2026-09-17 13:51:02`（上次关机时间，**落后 12 分**） |
| NTP 首次同步 | `95.111.202.5:123` | `2026-09-17 14:03:41`（**前跳 12 分 39 秒**） |

后果与对策：

- `dmesg -T`、`journalctl` 默认格式、`docker inspect` 墙钟字段**互相矛盾**，不能直接排序。
- **一律用单调时钟**：`journalctl -b -o short-monotonic`、裸 `dmesg`、`/proc/uptime`。
- 任何用墙钟做超时/排序/去重的逻辑都可能被这 12 分钟前跳影响（ROS 侧已用 `use_sim_time` 隔离，见下）。

---

## 5. 已定位的具体缺陷

### 缺陷 1：livox 绑定早于 eth0 拿到静态 IP（必现竞争）

- **现象**：`bind failed` → `Create detection socket failed` → `Failed to init livox lidar sdk.` → `Init lds lidar failed!`
- **根因**：`/etc/slamibot/MID360_config.json` 的 `host_net_info` 四个 IP 写死为 `192.168.1.55`（eth0）；节点启动时该地址未就位，`bind()` 失败。
- **放大因素**：`sensors.launch:32` 的 `launch-prefix="bash -c 'sleep 0.5; $0 $@'"` 只给 0.5 秒，远不够。
- **影响**：`/livox/lidar` 零消息 → **`/clock` 无发布者** → 相机（等 timeshare）、拼接、`nav_multi`（等有效时钟）全部停摆 → 5001 空、红灯闪。
- **修复方向**（未实施）：
  - (a) 把 `launch-prefix` 的 `sleep 0.5` 换成"等该 IP 就绪再启动"。容器内**没有 `ip`/`ifconfig`/`ping`**，可用 `grep -q 192.168.1.55 /proc/net/fib_trie`（已实测：命中 2 行；不存在的 IP 命中 0）。IP 可硬编码或从 `MID360_config.json` 解析。
  - (b) 更彻底：让节点在 SDK 初始化失败时退出，使 `respawn` 生效（见缺陷 2）。
  - 风险：改 `sensors.launch` 会与"视频流压缩"线（另一 AI 正在改同一文件，未提交）产生合并点，虽大概率不重叠，但需协调先后。

### 缺陷 2：livox 初始化失败不退出 → respawn 永不触发

- **代码事实**（`src/livox_ros_driver2/src/livox_ros_driver2.cpp`）：

```cpp
 99|     if ((read_lidar->InitLdsLidar(user_config_path))) {
100|       DRIVER_INFO(livox_node, "Init lds lidar successfully!");
101|     } else {
102|       DRIVER_ERROR(livox_node, "Init lds lidar failed!");   // 只打日志
103|     }
...
108|   livox_node.pointclouddata_poll_thread_ = ...;   // 照样起线程
109|   livox_node.imudata_poll_thread_ = ...;
110|   while (ros::ok()) { usleep(10000); }            // 空转
111|
112|   return 0;                                        // 仅在 ros::ok() 变 false 时到达
```

- **关键认知**：`respawn` 是"进程退出才重启"，不是健康检查；退出码不影响 respawn（看退出码的是 `required="true"`）。**未触发的原因只是它没死。**
- **证据**：roslaunch 日志本次开机内唯一一次 `process has died` 是人工 `pkill`（`exit code -15` = SIGTERM）；此前零次。
- **来源**：厂商原始逻辑，非本项目引入（该文件历史仅 `init project` + 一次空白清理）。
- **修复方向**（未实施）：`else` 分支加 `ros::shutdown(); return 1;`（可独立成一个提交，便于单独 cherry-pick）。
- **注意与既有决策的关系**：1.0.17 的 `bb4a4a5` 明确选择"串口异常**不**退出、改为重试"，理由是退出会让整个状态页消失。该理由**不适用于雷达节点**（初始化失败时它本就无任何数据），但改动方向需团队确认。

### 缺陷 3：六麦模块启动慢/不稳定（硬件侧，非本仓库）

- 三段式枚举，本次 1098s 才可用；早前还出现过"能枚举但打开后几分钟 `DEGRADED_NO_WAKE`"的抽搐。
- 运行期现象：`[!] 音频状态: input overflow`。
- 影响：语音链路（`run_mic`）在设备可用后仍可能长时间不可用；supervisor 会等待并自动接上，但用户看到的是"语音没反应"。
- 待查：模块自身启动时间分布、是否与供电/前序端口 power cycle 相关。

### 缺陷 4：容器启动延迟（机理未明）

- 715：docker 守护 17.1s 就绪 → 容器 41.7s 才起（差 **24.6s**）；701 对照 53.3s。
- 已排除：设备上**没有**任何 systemd unit / `/etc/cron.d` / root crontab 在启动 compose 栈。
- 已知：容器 ID 跨重启不变（是 restart 而非 recreate）；`docker inspect` 显示 `FinishedAt≈41.2s` / `StartedAt≈41.7s`（相差 0.5s）。
- 待查方向：dockerd 恢复容器元数据/网络的耗时、`overlay2` 挂载、或与 NTP/`time-sync.target` 的隐式关系。需 dockerd debug 日志 + 探针量化。

---

## 6. 修复/优化备选（按优先级，均未实施）

| 优先级 | 项 | 类型 | 说明 |
|---|---|---|---|
| P0 | livox 启动门禁（等 IP 就绪） | 改 `sensors.launch`（+ 可选脚本） | 直接消除本次故障的必现竞争；改动最小 |
| P0 | 给雷达链路加"就绪"语义 | 设计 | 例如让 `/clock` 缺失可被检测并告警（现在它静默失效） |
| P1 | livox 初始化失败即退出 | 改 `livox_ros_driver2.cpp` | 让 respawn 具备自愈能力；可独立提交 |
| P1 | 六麦模块启动观测 | 硬件/测试 | 量化模块自身启动时间分布，判断是否需换线/换口/换模块 |
| P2 | 查清容器 24s 延迟 | 诊断 | 影响整体"上电到可用"时间 |
| P2 | 消除墙钟依赖 | 设计 | 确认全系统不依赖墙钟做超时/排序；或让 RTC 保电 |
| P3 | 启动链统一编排 | 架构 | 把"等前置就绪"的语义收进 launch/entrypoint，替代散落的 `sleep` |

---

## 7. 运行时恢复手册（已实测有效，无需改代码）

```bash
# 现象：/livox/lidar 有发布者但零消息、/dev/shm/timeshare 不存在、相机无图、5001 空、红灯闪
# 判据：容器内节点日志出现 "bind failed" / "Failed to init livox lidar sdk."

# 确认
docker exec firmware-sensors pgrep -af livox_ros_driver2_node
docker exec firmware-sensors bash -lc "ls -t /root/.ros/log/*/livox_lidar_publisher2-*.log | head -1 | xargs tail -12"

# 恢复（触发 respawn；respawn_delay=3）
docker exec firmware-sensors pkill -f livox_ros_driver2_node

# 验证（约 10 秒后）
docker exec scout-nav bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; \
  timeout 8 rostopic hz /livox/lidar | head -3; \
  timeout 8 rostopic hz /SLB_CAM_A/compressed | head -3; \
  timeout 5 rostopic echo -n1 /driver_status; \
  timeout 5 rostopic echo -n1 /topic_frequencies'
docker exec firmware-sensors ls -l /dev/shm/timeshare
```

本次恢复实测结果：`/livox/lidar` 10.000Hz、`/SLB_CAM_A/compressed` 9.936Hz、`/keyframe` 4.225Hz、`/topic_frequencies` `{"/livox/lidar":10.0,"/keyframe":4.0}`、`driver_status` 8→11、5001=200、timeshare 已创建。

---

## 8. 下一步

1. 用 `procedures/boot-stability-timeline-test-2026-09-17.md` + `tmp/boot_timeline_probe.sh` 在 715 与 701 各做 10 次冷启动，量化每一环耗时与失败率。
2. 依据探针输出确定 P0 修复是否足够（若"等 IP"后仍有失败，说明还有其它前置未满足）。
3. 修复走 Git 流程：本地/701 改源码 → 推云端 → 701 拉取编译 → 构建镜像 → 推 ACR → 升版本（**禁止跨系统直接拷文件**）。注意与"视频流压缩"线的文件冲突协调。
