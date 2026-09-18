# BOX USB 分支（`1-2.4`）掉线：现象、判据与恢复

- 首次记录：2026-09-17 18:00-18:45 CST（715 换松灵底盘期间）
- **最终根因：线材（USB 线）**——换另一根线后整支一次枚举成功
- 涉及硬件：**BOX 通过一根 USB 上行线接到机器人内部 hub 的 `1-2-port4`**；BOX 内部再分 `1-2.4.4` 子 hub
- 该分支下挂：**USB-CAN 适配器(candleLight)**、六麦阵列、三个 CH340（含 `lg_speech_serial`）、EC20/EC25 4G、C-Media USB 音频

---

## 0. 结论与教训（先看这段）

**`full-speed` + `device descriptor read/64, error -32` + `error -71` + `unable to enumerate USB device` ⇒ 先换线。**

本次在这上面绕了很多弯，值得记住的三点：

1. **"这根线在另一台车上是好的" 不等于 "它在这套电气条件下也是好的"。** 480M 高速 + 供电余量对线材很敏感；同一根线换设备/换负载就可能不达标。本次就是换线解决的。
2. **这类故障在软件层完全无解**：读不到设备描述符 = 内核连设备对象都没创建，udev / 驱动绑定 / `authorized` 都无从下手（`/sys/bus/usb/devices/1-2.4` 根本不存在）。
3. **内核在 `unable to enumerate` 之后不会再自己重试**；在其后面插拔下游设备**不会产生任何日志**。每次改动都必须**拔插上游那根线**（或给 BOX 断电重上电）才能触发新尝试——否则会误判成"什么都没发生"。

## 1. 现象（2026-09-17 715 实测）

坏线时：

```
[1879.4] usb 1-2.4: new full-speed USB device number 18        ← 只到"发现有个设备"
[1879.5] usb 1-2.4: device descriptor read/64, error -32       ← 读描述符失败（信号完整性）
[1880.2] usb 1-2-port4: attempt power cycle                    ← 内核自己重上电，无效
[1882.6] usb 1-2.4: Device not responding to setup address.
[1883.0] usb 1-2-port4: unable to enumerate USB device          ← 放弃
```

对照（同型号健康 hub `1-2.3`）：`new high-speed USB device ... idVendor=1a40, idProduct=0101`。
关键差异：**坏线只能跑 `full-speed`（12M），健康时是 `high-speed`（480M）**。

换线后（t=4246 起一次成功）：

```
usb 1-2.4:    New USB device found, idVendor=1a40, idProduct=0101   (BOX 内 hub, 480M)
usb 1-2.4.1:  Quectel EC25 LTE modem      (option/cdc_ether)
usb 1-2.4.2:  C-Media USB Audio
usb 1-2.4.3:  CH340
usb 1-2.4.4:  子 hub 1a40:0101 (480M)
    .1 CH340 / .2 gs_usb(candleLight CAN) / .3 ListenGo 六麦 / .4 CH340 → /dev/lg_speech_serial
```

---

## 2. 定位方法（把变量一个个拆开，每次只动一个）

| 步骤 | 操作 | 本次结论 |
|---|---|---|
| 1 | 适配器从 BOX 拔下，**直插 Jetson** | 出现 `1d50:606f candleLight` + `can0 UP` → 适配器 ✅、Jetson 该口 ✅ |
| 2 | `candump can0` | `0x221/0x241/0x251-254/0x261-262/0x311` 周期帧、`RX errors 0` → 底盘 ✅、CAN 接线 ✅、500k ✅ |
| 3 | BOX 接回（同一端口） | 仍 `full-speed` + `-32/-71` → **焦点收敛到"BOX 上行线 / BOX 内部 hub"** |
| 4 | **换一根 USB 线** | ✅ 整支一次枚举成功 → **定案：线材** |

> 附带确认：新底盘的适配器与旧的是不同物理设备（序列号 `0029004B4648570A20303731` vs 旧 `003700274148570C20343133`），且独立可用。

---

## 3. 恢复后**必须再做一步**：让节点重新打开 `can0`

`can0` 随 USB 消失时，**已运行的底盘节点持有的 socket 会失效**；网卡以新实例回来后，节点不一定自动重新 attach。表现：

```json
// GET /api/base_mode/status
"SCOUT": {"detected": true, "ready": false,
          "reason": "SCOUT_HEARTBEAT_STALE", "statusRecent": false}
"ready": false, "reason": "NO_READY_BASE_DETECTED"
```

`/scout_status` 显示 `no new messages`。**恢复动作（走它自己的门禁，含 can0 UP + RX 增长检查）**：

```bash
curl -s -X POST "http://127.0.0.1:5000/api/base_mode/switch?mode=scout"
```

本次两次表现不同，**稳妥做法都跑一次**：

- 18:22 那次：必须手工 `switch` 才恢复（`ready:true`、`/scout_status` 50.28 Hz）
- 18:41 换线后那次：**mode 已是 SCOUT，manager 自己接回来了**（`ready:true`、`statusRecent:true`）

## 4. 连带影响与自愈行为

同一支掉线会**同时**带走六麦阵列与 `lg_speech_serial` → 语音链路进入 `DEGRADED_NO_WAKE`（fail-closed 退出，supervisor 等待设备）。

- **语音：BOX 一回来会自己接上**（本次实测自动恢复，`WAIT_WAKE`）✅
- **CAN：可能需要手工 `switch` 一次**（见第 3 节）——这是两者的区别
- 串口编号会漂移（本次 `lg_speech_serial` 从 ttyUSB4 变 **ttyUSB8**），但 udev 规则按 **DEVPATH 路径**匹配，别名照样正确 ✅（不要依赖固定编号）

## 5. 设计层面的观察

- BOX 的"预留 Type-C 口"用于接底盘适配器（双 C 线）。该链路在旧底盘/旧适配器时是通的，所以不是结构性不可用。
- 但该分支的 USB 稳定性偏脆弱：本次为整支掉线（换线解决），此前还出现过六麦 `error -71` 枚举失败。
- 接线建议（择一）：①底盘适配器经 **C 转 A 线直插 Jetson**（已验证可用，绕开 BOX）；②BOX 侧改用 **USB-A 口 + A 转 C 线**（标准"主机 A / 设备 C"拓扑，不依赖 BOX 侧是否实现 CC 电路）。
- 下次遇到同类现象，**第一步换线**，不要先去查驱动/udev/绑定。

---

## 6. 复发记录：2026-09-18 上午（715）

**同一现象再次出现，且表现为"闪断"**（前一天换线后是好的，说明线材/接触仍在临界状态）。

### 时间线（均 715，CST）

| 时间 | 事件 |
|---|---|
| ~10:38 | BOX 分支出现：`/dev/lg_speech_serial -> ttyUSB4` 创建（10:38），`ttyUSB4` 出现（10:40） |
| 10:39 | 只读盘点：`lsusb` 见 `2208:0001`(六麦) + `0d8c:0012`(USB音频) + `2c7c:0125`(EC20 4G)；`/proc/asound/cards` 有 `card 2 USB Audio Device` + `card 3 ListenGo`；`run_mic` 正在跑（etime 1:52） |
| 10:45 | ModemManager：`state: failed`，`failed reason: sim-missing`（此时模块**在**总线上；**该机 BOX 确实没插 SIM**，用户已确认） |
| 10:48 | `aplay -D plughw:2,0` → `Device or resource busy`；nav 播报 job `TTS_FAILED`，日志 `TTS playback failed on plughw:2,0 (1)` |
| 10:52:37 | `run_mic` ALSA 启动失败 → `DEGRADED_NO_WAKE` 退出，supervisor 转入门禁等待 |
| ~11:00 | **BOX 分支 `1-2.4` 整个消失**：`lsusb` 只剩两个 CH340；`/proc/asound/cards` 只剩板载 HDA/APE；`/dev/lg_speech_serial` 不存在 |

### 现状判据（2026-09-18 11:00）

```
lsusb -t：
  Bus 01 Port 2 → Hub 1-2 → Port 3 → Hub 1-2.3 (1a40:0101)
      1-2.3.1 CH340   1-2.3.3 CH340   1-2.3.4 0fe6:9900 USB LAN
  ※ 1-2.4（BOX 上行分支）**完全不存在**，连失败的枚举记录都没有
journalctl -k（10:58 起）：
  usb 1-2.3.1: failed to send control message: -110     ← 保留下来的 CH340 也在超时
  ch341-uart ttyUSB1: failed to read modem status: -110
```

- **同时消失的整支**：Quectel EC20 4G、C-Media USB 音频、六麦阵列、`lg_speech_serial` —— 与本文 §0 描述的该分支挂载物**完全一致**
- `-110`（ETIMEDOUT）说明**电气链路仍不健康**，不只是"某个设备掉了"

### 教训补充（本次新增）

1. **「昨天还好、今天不行」优先怀疑这条分支，不要先怀疑软件。** 本次 4G 不通 + 到点播报不出声 + 唤醒失效，**根因就是这条分支掉线**（三者共用这条分支上的设备）。线插回后**三者同时恢复**，到点播报实测 `job=COMPLETED / played=True`。**注意别被自己带偏**：我中途一度把播报失败归因给 PulseAudio，实际那是我的诊断动作（`pactl`）自己制造的假故障，见下「结论」。
### 结论（2026-09-18 11:35，最终更正）——**到点播报本来就没坏，`EBUSY` 是我自己的诊断动作造出来的**

**用户是对的：源码版没有声卡抢占问题，是稳定的。** 我先前那条「PA 占卡是根因」的结论**作废**。

干净测试（**全程不调用 `pactl`**，静默 25s 后）：

```
宿主连续 4 次: rc=0  rc=0  rc=0  rc=0        ✓
nav 容器:      rc=0                          ✓
播放节点持有者: （/proc 扫，空 = 无人持有）    ✓
nav 端到端播报: job=COMPLETED  played=True   ✓
```

**机制（我把自己坑了）**：`pactl`（以及任何 PA 客户端）一连上去，就会把 sink 从
**`SUSPENDED` 唤醒成 `IDLE`**；而 `IDLE` 恰恰代表 **PA 打开了声卡**。于是：

```
pactl 一调用 → sink 变 IDLE → PA 持有 /dev/snd/pcmC0D0p → aplay -D plughw:0,0 → EBUSY
```

我先前那张「IDLE=rc1 / SUSPENDED=rc0」的可逆对照表**本身是成立的**，但它的因果被我读反了：
**不是 PA 平时在占卡，而是我的查询动作让 PA 占上了卡。** 于是我在「自己制造的故障」里越陷越深，
还据此提出要 mask PulseAudio —— **该建议撤回，不需要动 PA。**

**正确做法（写死在这里，别再犯）**：

- **测 ALSA 播放时不要碰 `pactl` / `paplay` / 任何 PA 客户端。** 要查 PA 状态就一次性查完，
  或者干脆只看 `/proc/*/fd` 与 `lsusb -t`。
- 判断顺序：① 整支 USB 是否在位（`lsusb -t` + `/proc/asound/cards`，连续几次不变）
  → ② 直接 `aplay -D plughw:<card>,0` 并**取退出码** → ③ 才轮到 nav 端到端播报。
- **`fuser` 看不到 PA**（它用 mmap/非独占方式持有），要用 `/proc/*/fd` 扫。

### 仍然有效的观测纪律

**判据优先级**：先看「整支 USB 是否在位」，再谈「谁占了设备」。**设备在闪断时，任何根因结论都不可靠。**
另一个具体教训：**必须取退出码**。`aplay` 打印 `Playing raw data ...` 只是启动提示，
不代表打开成功 —— 我因此得出过一次错误结论。本次更严重的一条是
**观测者效应：诊断动作本身改变了被测系统**，这类错误靠"再测一次"是发现不了的，
必须换一种**不扰动**的观测手段（或先停下所有干预，静默一段时间再测）。
另一个具体教训：**取退出码**。`aplay` 打印 `Playing raw data ...` 只是启动提示，
**不代表打开成功**；不带 `rc=$?` 的测试会给出错误结论（我犯过一次）。
2. **`/proc/asound/cards` 是最快的单点判据**：USB 音频与六麦是同一条分支，一起消失就是分支问题。
3. 设备掉了之后，`aplay` 的报错会从 `Device or resource busy` 变成 `Invalid value for card` / `No such file or directory` —— **同一个根因的两种阶段**，不要当成两个故障。

### 断电重启后的决定性证据（2026-09-18 11:12–11:15）

用户断电重启 + 插上 SIM 后复测，内核日志给出**与 §0 完全一致的签名，且这次出现在分支根 `1-2.4` 本身**：

```
usb 1-2.4: new full-speed USB device number 95 using tegra-xusb   ← 只有 full-speed(12M)，健康时是 high-speed(480M)
usb 1-2.4: Device not responding to setup address.
usb 1-2.4: device not accepting address 95, error -71
```

- **本次启动累计枚举失败 26 次**；`1-2.4` 分支在重启后 3 分钟内**枚举到一半又断**
- 中间曾有短暂窗口整支正常：`1-2.4.1` EC20 4G、`1-2.4.2` C-Media 音箱（`card 0 [Device]`）、`1-2.4.3`/`1-2.4.4.1` CH340 都上了；**只有 `1-2.4.4.3`（六麦）单独失败**：
  ```
  usb 1-2.4.4.3: device descriptor read/64, error -110
  usb 1-2.4.4-port3: attempt power cycle        ← 内核自己重上电，无效
  usb 1-2.4.4.3: Device not responding to setup address.
  ```
- 结论不变：**先换线**。且「`full-speed` + `error -71` + `Device not responding to setup address`」这组签名本次再次命中。

**一条重要教训（观测纪律）**：在设备闪断期间**任何"根因"结论都不可靠**。本次我在「PA 占声卡」和「设备掉线」之间来回摇摆过一次，原因是观测窗口本身在变。**正确顺序：先确认整支 USB 稳定在位（连续多次 `lsusb -t` + `/proc/asound/cards` 不变），再去做"谁占了设备"这类二级归因。**

