# 715 固件 WEB 状态全空：STM32/RTK 两个 CH340 在容器重建瞬间挂死

- 日期：2026-09-17
- 设备：715 = `jetson@192.168.31.164`；对照 701 = `192.168.31.135`
- 状态：**根因已定位（串口挂死 + 固件不健壮）；非镜像缺件；容器重建是触发点**

## 一、现象

- `http://192.168.31.164:5001/` 页面能打开（200，47276 B），但**频率/相机/雷达/电池/温度等状态全空**。
- 对应话题无发布者：`/topic_frequencies`、`/system_monitor_history`、`/cpu`、`/memory`、`/battery`、`/storage`、`/driver_status`。

## 二、排除"镜像漏件"

| 检查 | 结果 |
|---|---|
| 5001 页面本体 | 715(1.0.16) 与 701(旧镜像) **逐字节相同**（47276 B，`diff` 无差异） |
| `/static/main.js` | 两台**相同**（62338 B）；连接地址 `'ws://' + location.hostname + ':9090'`（正确） |
| 数据来源 | 页面用 roslib 订阅 `/topic_frequencies` 等，全部由 core 容器的 **`SystemMonitor`** 发布 |
| 二进制/launch | 两台镜像内 `project_control/SystemMonitor` 均在；`core.launch:4` 均声明该节点 |
| 701 运行态 | `/system_monitor` 正常（PID 63）→ 701 状态页有数据 |

## 三、两台的 USB 拓扑实测（**不一样**，功能相对位置一致）

| | 701 | 715 |
|---|---|---|
| CH340 组所在 hub 支 | **`1-2.1`** | **`1-2.3`** |
| `.1` | CH340 → `ttyUSB0` = **ttyRTK** | CH340 → `ttyUSB1` = **ttyRTK** |
| `.3` | CH340 → `ttyUSB1` = **ttySTM32** | CH340 → `ttyUSB0` = **ttySTM32** |
| `.4` | `0fe6:9900` USB-LAN → **eth0 = 192.168.1.55（雷达网口）** | 同左 → eth0 = 192.168.1.55 |
| 额外支 | 无 | `1-2.4`（EC20 4G、USB 音频 `0d8c:0012`、CH340、CAN `1d50:606f`、ListenGo 六麦阵列 `2208:0001`）+ 子 hub `1-2.4.4` |
| 其它 | OAK 在 `2-1.3` | OAK 在 `2-1.1`；**`2-1.2` 插着 Kingston U 盘 `0951:1666`** |

结论：**相对布局一致**（同一支 hub 下 `.1`=RTK、`.3`=STM32、`.4`=雷达网口），但**物理口路径号不同**（701=`1-2.1.x`，715=`1-2.3.x`）。
→ **715 的 `ttySTM32`/`ttyRTK` 别名是"指对了"**：它们指向的正是与雷达网口同在 `1-2.3` 支上的两个 CH340。

## 四、根因

```
t=9.7s   1-2.3.3 new full-speed device (1a86:7523) -> ttyUSB0 (ttySTM32)   ← 正常
t=11.2s  1-2.3.1 new full-speed device (1a86:7523) -> ttyUSB1 (ttyRTK)    ← 正常
t=13.5s  两个 ch341-uart converter now attached
...      （约 2 小时内无异常）
t=7168s  usb 1-2.3.1/.3: failed to send control message: -110             ← 首次故障
t=7170s  ch341-uart ttyUSB1/ttyUSB0: failed to read modem status: -110
```

- 开机时间 `09:05:36`，`t=7168s = 11:05:04` —— **正好是我执行 `docker compose up -d` 重建 core 容器的时刻（容器 StartedAt = 11:05:01）**。
- 即：这两个口从开机到 11:05 一直是**健康**的；重建 core（旧 SystemMonitor 被销毁）之后双双变成 `-110` 超时，打开返回 `EIO`。
- 芯片**并未电气损坏**：`lsusb -v -s 1:6` / `1:8` 均能正常返回描述符（同为 CH340 的 `1-2.4.3` 也正常）；同 hub 上的 USB-LAN（1-2.3.4）一直在跑雷达数据 → **hub 与供电正常**。属典型 CH340 挂死（持有进程被销毁后芯片留在半配置态，需 USB 端口复位）。
- 后果链：`SystemMonitor` 打不开串口 → **干净退出**，而 `core.launch` **无 respawn** → `/topic_frequencies` 等全部无人发布 → 5001 状态页全空、APP 的 `/driver_status` 也没有；`ntrip_rtk_service` 同样打不开 `ttyRTK`。**LED 不亮同源**（`LEDControl` 走同一条 STM32 串口）。

## 五、更正记录（我前后两次判断都错）

1. 首次："设备被拔插过" —— 错。那些 `usb 1-2.1 / 2-1.1: USB disconnect` 是 **OAK 相机**（`03e7:f63c` Bootloader ↔ `03e7:f63b` Device）自身模式切换。
2. 其次："715 的 udev 规则按旧拓扑写、别名指错口" —— 错。实测两台的**相对布局一致、绝对路径号不同**，715 的别名指向真实存在的 STM32/RTK 口。
3. 另：我第一次"715 的 1-2.1 从无 CH340"的检查方法无效（把 `idVendor` 与端口号放同一行 grep，而内核日志本就分两行）。

## 六、真正的缺口与建议

1. **先是恢复**：对 `1-2.3.1` / `1-2.3.3` 做软件 USB 端口复位（`USBDEVFS_RESET` 或 unbind/bind）。⚠️ 风险：若 CH340 的 DTR/RTS 接到 STM32 的复位/BOOT 引脚（与 IAP 刷写电路同源），复位可能让 STM32 重启甚至停在 Bootloader，需重新 `runapp` 才恢复 FSIN（相机）。**建议改为整机断电重启**（对出货设备也最干净）。
2. **固件健壮性（建议进 1.0.17，对所有出货设备都重要）**：
   - `SystemMonitor` / `ntrip_rtk_ros_service`：串口打不开时**不要退出**，改为记录 + 周期重试（其它状态照常发布）；
   - `core.launch` 关键节点加 `respawn="true"`；
   - 串口打开失败重试/重开路径，避免"容器重启即挂死串口"这种一次性故障演变成整页状态消失。
3. **715 udev 规则确实缺两条别名**（与 1-2.3 无关）：
   - `ttyDOG`/`ttySBUS`：写成 `1-2.4.2`，而 715 的 `1-2.4.2` 是 **USB 音频设备**（`0d8c:0012`，不匹配 1a86:7523）→ 该别名永远建不出来；701 的规则已改为 `1-2.4.3`；
   - `lg_speech_serial`（BOX 六麦阵列）：715 规则里**整条缺失**，CH340 实际在 `1-2.4.4.4`（ttyUSB8）；
   - `77-mm-ignore-usb0.rules`（防 ModemManager 抢串口）715 缺失。
4. **出货前数据面**：715 的 USB3 口上插着一个 **Kingston DataTraveler U 盘**（`2-1.2`，`0951:1666`），不是设备本体的一部分，出货前应取出并确认未挂载。
5. 未做：以上均为**建议**，本轮只做只读取证（除按用户要求删除 715 的 compose 备份与无用镜像）。

## 七、2026-09-17 处理结果（已闭环）

1. **用户整机断电重启后，两个串口自愈**：`/system_monitor`、`/ntrip_rtk_service`、`/led_control` 全部自动起来；
   重启后 `ttyRTK -> ttyUSB0`、`ttySTM32 -> ttyUSB1`（编号变了，但按 USB 路径匹配的别名仍正确——这正是必须用 `KERNELS==` 而不是 ttyUSB 编号的原因）。
2. **状态链路已恢复并实测**（重启后约 1.5 分钟 SystemMonitor 才开始发布，此前 hz 报 "no new messages" 属初始化窗口）：
   `/topic_frequencies`（样本 `{"/livox/lidar": 11.0, "/keyframe": 5.0}`）、`/battery`（约 1 Hz）、`/cpu` 36.7、`/memory` 24.8、`/storage` "6G/230G"、`/camera_temperature` 77.49、`/driver_status` 11（UInt8）。
   5001 的 HTTP 接口同样 200 且有数据：`/api/wifi/status`（connected, ssid=slamibot）、`/api/hotspot/status`、`/api/frpp/status`（active）。
3. **BOX 串口绑定已做**（用户授权）：`/etc/udev/rules.d/99-serial-aliases.rules` 追加
   `KERNELS=="1-2.4.4.4" → SYMLINK+="lg_speech_serial", MODE:="0777"` → `udevadm control --reload-rules && udevadm trigger --subsystem-match=tty`
   → 实测 `/dev/lg_speech_serial -> ttyUSB4`，DEVPATH 确认为 `1-2.4.4.4`（ListenGo 六麦阵列的控制 CH340）；复合设备里的 `ttyACM0` 保持不用。

### 规则到底在哪（重要）
**不在 Docker 镜像里**，在**宿主** `/etc/udev/rules.d/`，由公开仓库 `d360_deploy` 的 `udev_rules/setup_udev_rules.py` 写入（`setup_env.bash` 第 65-80 行 wget 后用 sudo 执行，再 `udevadm control --reload-rules` + `trigger`）。脚本会写三个文件：`80-movidius.rules`、`99-serial-aliases.rules`、`99-usb-auto-mount.rules`。

该脚本的两个问题（715 现状正是它造成的）：
- **模板里没有 `lg_speech_serial`**（也没有 `ttySBUS`）→ 任何设备一键装机后都不会绑定 BOX 串口；
- 自动探测失败时回落到硬编码默认值 `1-2.3.3 / 1-2.3.1 / 1-2.4.2`，而 715 的规则文件内容与之**逐字一致** → 说明当时探测失败（串口被占用或没数据）后写了默认值。

（701 的规则文件是**手工改过**的：注释记录了拓扑变更、加了 `ttySBUS` 与 `lg_speech_serial`。所以两台文件的差异来自人工修改，不是脚本版本差异。）

### 仍未处理（待授权）
- **`ttyDOG`/`ttySBUS` 规则指向 1-2.4.2**，而 715 的 1-2.4.2 是 USB 音频设备（`0d8c:0012`，不匹配 `1a86:7523`）→ 该别名永远建不出来（701 已改为 `1-2.4.3`）。
- `77-mm-ignore-usb0.rules`（防 ModemManager 抢串口）715 缺失。
- **持久修复应改脚本**：在 `d360_deploy/udev_rules/setup_udev_rules.py`（以及固件仓库里的同名副本）补 BOX 规则、`ttySBUS`、并修正 DOG 默认值 —— 否则下一台新设备还会缺。
- **固件健壮性**：`SystemMonitor`/`ntrip_rtk_ros_service` 串口打不开时不要退出 + `core.launch` 加 `respawn="true"`，这样"容器重建挂死串口"这类故障能自愈（现在只能靠断电重启）。
- **出货前**：715 的 `2-1.2` 上插着 Kingston DataTraveler U 盘，应取出。
