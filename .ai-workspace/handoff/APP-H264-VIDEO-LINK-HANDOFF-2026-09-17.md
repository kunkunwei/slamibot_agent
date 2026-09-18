# APP 交接文档：H.264 低带宽视频链路（机器人侧已实现）

> ## ⛔ 本文档已作废（2026-09-17 深夜）—— 不要照它实现
>
> **H.264 方案已被用户否决，全线移除。** 实时画面改回**导航侧 MJPEG 压缩链路**，压缩强度定为 **50%**（不再压 95%）。
>
> - 固件侧：H.264 代码已 revert（GitHub `kunkunwei/SLAMIBOT_D360` main `e799f1b`，−994 行）→ **5010 端口不再存在**
> - APP 侧：H.264 客户端已删除（`F:\SLAMIBotApp` 提交 `047d9d6`，其后只剩 `MjpegStreamView`，视频固定走 `?profile=video_link`）
> - **新方案见**：`.ai-workspace/handoff/MJPEG-VIDEO-LINK-TUNE-50PCT-HANDOFF-2026-09-17.md`
>
> 本文保留仅为**历史记录**（记录当时定稿的协议与实现细节，便于日后需要时快速还原）。**不要在 5010 / Annex-B / MediaCodec 这条路上再做实现。**
>
> 唯一仍然有效、且已落地到 APP 的两条结论：**① 分辨率恒定不降、只按带宽调压缩率；② 按机型选相机（新机型前相机 = `CAM_A`）。**

- 日期：2026-09-17
- 服务端：固件镜像 `slamibot_d360_firmware`（相机节点 `oak_hardware_trigger_ros` 内嵌）
- 客户端：`F:\SLAMIBotApp`（Kotlin / Compose，分支 `codex/native-compose-filament`）
- 交接范围：**APP 侧改动由你完成**；协议、服务端、参数阶梯已定稿，不需要再协商

---

## 1. 一句话结论

机器人侧新增一条 **WebSocket + 裸 H.264（Annex-B）** 实时视频链路，用来替代现有 MJPEG 链路：

| | 现状（MJPEG） | 新链路（H.264） |
|---|---|---|
| 默认档带宽 | 20–23 Mb/s（不重编码） | **10 Mb/s**（最高档） |
| 低带宽档 | 0.92 Mb/s 但画面被压到 480px / Q20（糊） | **3 Mb/s，仍是 1920×1200 / 10fps**，只是压缩率更高 |
| 帧率 | 10 fps | 10 fps（不变） |
| 分辨率 | 可被服务端降到 160px | **恒定 1920×1200，永不降分辨率** |
| 自适应 | 服务端单向压，无画质下限 | 服务端按实测链路积压 **+ 真实丢帧率** 自动在 `tiers_kbps` 之间切档（档数由设备配置决定，通常 2 档） |
| APP 依赖 | OkHttp + BitmapFactory | **OkHttp WebSocket + MediaCodec，无需新增任何第三方依赖** |

## 1.1 前置条件（先读这一节）

- **这条链路默认是关闭的**，按机型在 `/etc/slamibot/video_link.json` 显式开启（`{"enable": true, "camera": "CAM_A", "tiers_kbps": [10000, 3000]}`）。
  - 原因：OAK 同时**最多 5 个视频编码器**，而三路相机各要一个 MJPEG 供 `/keyframe` 拼接（**空间重建的输入，不可牺牲**）。默认打开会在没有配置文件的设备上挤掉一路相机 —— 现象是「相机已连接、publisher 存在，但完全没有帧」，代价是 `/keyframe` 断流、建图不可用。**所以 H.264 最多只能占 2 档。**
- **相机要按机型配**：715 是 `CAM_A`=前(中间) / `CAM_B`=左 / `CAM_C`=右；701 老款顺序不同。配错会看到侧面画面。
- **档位数量不固定（1~2 档），APP 不要硬编码**：一律以 `hello` 里的 `tiers_kbps` / `tier` 为准。本文档示例写 3 档只是格式示意。
- `serving: false`、5010 连不上、或 `hello` 没来 → **APP 按原逻辑回退 MJPEG**（`profile=video_link`）。

**APP 不需要上报任何信息、不需要重连、不需要自己判断带宽**：切档完全由服务端决定，并且切档时流不中断。

---

## 2. 端点与协议

### 2.1 连接

```
ws://<host>:5010/api/camera/stream.h264
```

- 端口 **5010**（容器是 `network_mode: host`，直接可达）。
- `<host>` 与现有导航 API 同一个 IP（如 715 = `192.168.31.164`）。
- 不需要子协议（`Sec-WebSocket-Protocol`）。
- 明文 `ws://` 即可（`AndroidManifest.xml:30-31` 已放开 cleartext）。

### 2.2 消息格式

连接建立后，服务端**先发一条文本消息**，之后**只发二进制消息**。

**(a) 文本消息 = JSON hello（仅第一条）**

```json
{
  "type": "hello",
  "codec": "h264",
  "container": "annex-b",
  "width": 1920,
  "height": 1200,
  "fps": 10.0,
  "tier": 0,
  "tiers_kbps": [10000, 3000],
  "adaptive": true
}
```

用途：确认链路可用 + 拿到分辨率用于配置解码器。`width/height/fps` 是**恒定值**，不会中途变化。

**(b) 二进制消息 = 一个 H.264 access unit（一帧）**

- 编码：H.264 **Main profile**，CBR，`numBFrames=0`
- 封装：**Annex-B**，起始码是 **4 字节 `00 00 00 01`**
- 每个 access unit **以 AUD（NAL type 9）开头**
- 关键帧（每 10 帧 = 1 秒）包含 `AUD + SPS(7) + PPS(8) + IDR(5)`
- 非关键帧只有 `AUD + 1..n 个非 IDR slice`

实测样例（1920×1200 @10fps，最高档 10 Mb/s）：

```
frame  0 len= 30444  nals=AUD,SPS,PPS,IDR      <- 关键帧
frame  1 len=    80  nals=AUD,non-IDR
frame  2 len=  6473  nals=AUD,non-IDR
frame 10 len=627001  nals=AUD,SPS,PPS,IDR      <- 关键帧
```

> 关键性质：**一条 WebSocket 二进制消息 = 一个完整 access unit**。APP 不需要自己做帧边界切分，直接把消息体喂给 `MediaCodec` 的 input buffer 即可（`00 00 00 01` 起始码格式 `MediaCodec` 原生支持）。

### 2.3 诊断接口（非必需，排障用）

```
GET http://<host>:5010/api/camera/stream.h264/status
```

```json
{
  "codec": "h264", "stream": "SLB_CAM_B/h264",
  "width": 1920, "height": 1200, "fps": 10.0,
  "tier": 0, "pending_tier": null,
  "tiers_kbps": [10000, 3000],
  "adaptive": true,
  "clients": 1,
  "backlog_bytes": 0,
  "window_min_bytes": 0,
  "delivered_mbps": 9.87,
  "switches": 0,
  "serving": true
}
```

`tier` 越小画质越高（`0` = 10 Mb/s，`2` = 1.5 Mb/s）。`serving: false` 或连不上 = 服务端未启动，请回退 MJPEG。

### 2.4 调试用：强制固定档位

```
ws://<host>:5010/api/camera/stream.h264?tier=2
```

带上 `tier=` 会**全局停用自适应**并锁定该档（只用于验证画质/带宽，不要在产品逻辑里用）。不带参数时 `hello.adaptive = true`。

---

## 3. 服务端切档行为（APP 需要知道的全部）

1. **分辨率恒定**：任何档位都是 1920×1200。所以 `MediaCodec` 不会收到 `INFO_OUTPUT_FORMAT_CHANGED`，不需要处理尺寸变化。
2. **切档不中断、不花屏**：服务端在目标档出现 `SPS+PPS+IDR` 之后才切换输出（关键帧每 1 秒一个，所以最坏 1 秒内完成）。切换后 APP 收到的是新档的关键帧，解码器可直接继续。
3. **切档不需要重连**：同一条 WebSocket 连接内发生，APP 无感。
4. **慢客户端只会丢帧，不会积压**：服务端对每个客户端只保留"最新一帧"，链路变差时表现为**掉帧**而不是延迟累积（这正是解决坐标/画面滞后问题所需要的）。
5. **自适应阈值**：服务端每 0.5 秒采样一次内核发送队列积压（`SIOCOUTQ`）并统计实际发送码率。**积压超阈值** 或 **实发码率低于当前档目标码率的 85%** 都判为拥塞；降档需连续 2 秒确认，升档需连续 10 秒稳定，最小切换间隔 5 秒。降档后有 **120 秒升档冷却**，避免在临界带宽上反复抖动（链路真的恢复时最多 2 分钟就会自己升回去）。

---

## 4. APP 侧实现要点（Kotlin）

### 4.1 依赖：**不需要新增任何 Gradle 依赖**

已核实 `app/app/build.gradle.kts:83-105` 与 `app/gradle/libs.versions.toml` 中**没有** ExoPlayer/Media3、没有 WebRTC、没有 VLC/ijkplayer，也没有任何 `MediaCodec` 使用。本方案只用：

- `okhttp3:okhttp:4.9.3`（**已在用**，`RosbridgeSession.kt:265` 等 5 处已用 `newWebSocket`）
- `android.media.MediaCodec` / `MediaFormat`（系统 API，minSdk 29 足够）
- `android.view.SurfaceView`（系统 API）

> 备选方案对比（不推荐）：ExoPlayer RTSP 需要新增 `media3-exoplayer-rtsp` + 服务端另起 mediamtx/ffmpeg（镜像里**没有 ffmpeg**，且 mediamtx 在宿主未运行）；WebRTC 需要引入原生库。两者都比本方案改动大、依赖多。

### 4.2 需要改的文件

| 文件 | 改动 |
|---|---|
| `app/app/src/main/java/com/example/metacam/RobotEndpoint.kt:26-43` | 新增 `h264StreamUrl = "ws://$host:5010/api/camera/stream.h264"`；**删掉 `VIDEO_LINK_HOST`/`profile=video_link` 的 host 硬编码判定**（现在只对 `192.168.144.87` 生效，是历史遗留） |
| **新增** `H264StreamClient.kt` | 参考现有 `MjpegStreamClient.kt:31` 的结构（OkHttp 流式客户端 + 单线程 Executor + latest-only 丢帧），改成 WebSocket 回调 + MediaCodec |
| **新增** `H264StreamView.kt` | 用 `SurfaceView` + `MediaCodec.createDecoderByType("video/avc")` 渲染，替换 `MjpegStreamView` 的 `Canvas.drawBitmap`（`MjpegStreamClient.kt:115,181-197`） |
| `NativeNavigationSession.kt:119-124, 357-372` | 视频开关按传输类型分派：H.264 优先，失败回退 MJPEG |
| `NativeNavigationScreen.kt:742-766` | `AndroidView` 里换成新的 `H264StreamView`（卡片尺寸 320dp×160dp 不变） |

### 4.3 MediaCodec 配置（关键步骤）

```kotlin
// 1) 先收到文本 hello → 拿到 width/height
// 2) 等第一个二进制消息（含 AUD+SPS+PPS+IDR），从中抽出 SPS(7)/PPS(8)
val format = MediaFormat.createVideoFormat("video/avc", width, height).apply {
    setByteBuffer("csd-0", sps)   // 含 4 字节起始码
    setByteBuffer("csd-1", pps)
}
val codec = MediaCodec.createDecoderByType("video/avc")
codec.configure(format, surface, null, 0)   // surface 来自 SurfaceView
codec.start()
// 3) 之后每条二进制消息 = 一个 access unit，直接送 input buffer
val idx = codec.dequeueInputBuffer(10_000)
if (idx >= 0) {
    val buf = codec.getInputBuffer(idx)!!
    buf.clear(); buf.put(accessUnit)
    codec.queueInputBuffer(idx, 0, accessUnit.size, presentationTimeUs, 0)
}
// 4) 持续 dequeueOutputBuffer + releaseOutputBuffer(idx, false)  // false = 不重绘，低延迟
```

要点：
- `presentationTimeUs` 用本地单调时钟自增即可（服务端不发 PTS）；`dequeueOutputBuffer` 用超时 0，只取当前可用的。
- **不要**用 `MediaExtractor`——裸流没有容器。
- 若第一帧不是关键帧（理论上不会，服务端保证 hello 后第一帧就是关键帧），丢弃直到遇到含 SPS 的帧。
- 低延迟可选：`MediaFormat.KEY_LOW_LATENCY`（API 30+，`minSdk 29` 需运行时判断）+ 输出 surface 不要开 `setFixedSize` 之类的额外缓冲。

### 4.4 断线与回退

```
连 ws://host:5010/api/camera/stream.h264
  ├─ 连接失败 / 3 秒内没有 hello        → 回退 MJPEG
  ├─ 5 秒内没有任何二进制帧             → 回退 MJPEG
  └─ 正常播放中连接断开                 → 退避重连（1s/2s/4s，上限 10s），
                                          连续 3 次失败再回退 MJPEG
回退：http://<host>:5000/api/camera/stream.mjpeg?profile=video_link   （现状逻辑，保持不变）
```

回退路径**不需要改**：现有 `MjpegStreamClient` + `profile=video_link` 保留（服务端 `capture.py` 不动）。

---

## 5. 验收标准（请按这几条测）

1. 715（`192.168.31.164`）打开建图/作业 → 导航页视频能出画，画面清晰、无明显马赛克。
2. `adb logcat` 能看到：连接成功 → 收到 hello（打印 width/height/tier）→ 解码帧率稳定 **≈10 fps**。
3. 与旧 MJPEG 对比：**画面更清楚**，且端到端延迟不增加。
4. 拔掉/弱化网络（或用路由器限速到 2 Mb/s）→ 服务端日志出现 `[H264Link] 切档 -> t2`，APP **不需要重连**，画面继续出（可能略糊但不卡、不延迟累积）；限速恢复后约 10 秒自动回到 t0。
5. 排障用：`curl http://192.168.31.164:5010/api/camera/stream.h264/status` 能看到 `tier` / `delivered_mbps` / `backlog_bytes`。

---

## 6. 已知边界（不是 bug）

- 链路只推 **CAM_B 一路**（与现有 `ros_client.py:461 CAMERA_TOPIC=/SLB_CAM_B/compressed` 一致）。多路切换是后续需求。
- 10 fps 是**硬件决定的**（STM32 `TIM2` PA1 硬触发，`F:\slamibot_stm32\USER\main.c:49` `TIM2_PWM_Init(999, 7199)` = 10.000 Hz），本方案**不改变帧率**，只降低同样帧率下的字节数。
- 数据采集（建图关键帧）走的仍是 rosbridge `/keyframe`，与本链路无关，未改动。
- 服务端端口 5010 被占用时会放弃启动 H.264 链路（相机不受影响），此时 `status` 不可达 → APP 走回退。
