# 701 六麦阵列与 USB 音箱未枚举（`lg_speech_serial` 别名规则 devpath 不匹配）

- 发现时间：2026-09-18 10:10–10:30 CST（701 `jetson@192.168.31.135`，开机 1h33m）
- 状态：**未修复**（属物理/拓扑状态，需现场处理；本文只记录现象与判据）
- 影响：**语音链路完全不可用**——宿主与容器同样受影响，不是容器化引入的回归

## 现象

| 检查项 | 结果 |
|---|---|
| `lsusb` 六麦阵列 UAC `2208:0001` | **不存在** |
| `lsusb` USB 音箱 `0d8c:0012` | **不存在** |
| `ls /dev/lg*` | 无（`/dev/lg_speech_serial` 未生成） |
| 宿主 `arecord -l` / `aplay -l` | 只有 Jetson 板载 `card 0 HDA` / `card 1 APE`，无 ListenGo、无 USB Audio Device |
| 宿主 `/proc/asound/cards` | 只有 `HDA` + `APE` |
| `/dev/ttyUSB0`、`/dev/ttyUSB1` | 存在（两个 CH340 `1a86:7523`） |

## 根因（已定位）

`/etc/udev/rules.d/99-serial-aliases.rules:16` 要求：

```
KERNEL=="ttyUSB*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", KERNELS=="1-2.4.4.4", SYMLINK+="lg_speech_serial"
```

而当前两个 CH340 的实际 devpath 是 **`1-2.1.1` 和 `1-2.1.3`**，不是 `1-2.4.4.4` → 规则不匹配 → 别名不生成。

`1-2.4.4.4` 意味着「总线1 → 端口2 → 端口4 → 端口4 → 端口4」这条特定的集线器链（BOX 挂在那条链上）。当前拓扑变成了 `1-2.1.x`，说明 **BOX 的 USB 没接在规则预期的端口/集线器链上**（或该链上的设备未上电）。六麦 UAC 与 USB 音箱同样不在总线上，与「BOX 整体未就绪」一致。

## 与已知现象的关系

- 六麦模块是**独立嵌入式 Linux**，上电后自己走三段启动（`1f3a:efe8` → `18d1:d002` → `2208:0001`），最坏十几分钟（见 `d360-cold-boot-stability-analysis-2026-09-17.md:19,96`）。
- 但本次它在 `lsusb` 里**连第一段都没出现** → 不是「还没启动完」，更像**物理连接/端口变了**或 BOX 未上电。
- 这与 `.ai-workspace/known-issues/715-serial-ports-hung-status-page-empty-2026-09-17.md:66,90` 记录的「701 的规则文件是手工改过的、加了 `lg_speech_serial`」相关：**规则里的 devpath 是硬编码的，换端口就失效**。

## 语音栈的实际行为（符合设计，不是缺陷）

`sherpa.log` 显示 run_mic 曾成功自动选中 `ListenGo Circular 6-Microphone: USB Audio (hw:3,0)`，随后 ALSA 启动失败：

```
Expression 'alsa_snd_pcm_start(...)' failed ... 
[安全] 唤醒读取线程失效，进入 DEGRADED_NO_WAKE；禁止 HTTP 派发
[*] 进程保持 fail-closed；1秒后退出，由supervisor等待设备恢复并重启。
2026-09-18T10:13:37+08:00 sherpa exited rc=3; retrying in 5s
```

即 fail-closed + 等设备恢复，**这是正确行为**；门禁条件（`/dev/lg_speech_serial` + `arecord -l` 见 ListenGo + `aplay -l` 见 USB Audio Device）不满足时不会起 run_mic。

## 待现场处理（需授权，未执行）

1. 确认 BOX 供电与 USB 连接；确认它接回规则预期的集线器链。
2. 若拓扑确实永久变了：把规则里的 `KERNELS=="1-2.4.4.4"` 改成实际 devpath（**禁止猜**，用 `udevadm info -q path -n /dev/ttyUSBx` 取实际值），或用 `install_extra_serial_aliases.sh` 的自动探测版（它先 `find_listengo()` 再找同级 CH340）。
3. 设备回来后按 `procedures/boot-stability-timeline-test-2026-09-17.md` 复验。

## 对容器化的影响

语音容器的门禁会**等待**这些设备（与宿主 supervisor 行为一致），不会崩、不会误派发。容器本身已验证就绪（`PASS=16 / FAIL=0 / BLOCKED=3`，3 项 BLOCKED 全部是本文这三条设备条件）。
