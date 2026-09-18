# APP 交接文档：开始作业页预览改用独立 HTTP MJPEG（10 fps，位姿不再被阻塞）

> ## ✅ 已实现并真机验收（2026-09-18）—— 本文档转为留档参考
>
> - **APP 侧已按本文实现**：提交 **`5be6646`**（`feat(collection): pull the camera preview over HTTP MJPEG`）+ 版本 **`28eac63 release: v1.6.8`**，**均已推送**。改动 **3 个文件 +73/−4**：`NativeDataCollectionSession.kt`(+70)、`RobotEndpoint.kt`(+6)、`RobotEndpointTest.kt`(+1)；**`NativeDataCollectionScreen.kt` 一行未改** ✓
> - **命名以实际实现为准**：`RobotEndpoint.previewPort(5010)` + **`cameraPreviewUrl`**（本文 §5 里建议的 `collectionPreviewUrl` 未采用；实际命名与同文件既有的 `cameraStreamUrl` / `videoLinkCameraStreamUrl` 保持一致，这样更好）。
> - **实测数字以真机为准**：预览 **9.92–10.04 fps**、单帧 **~60 KB**、**≈4.8 Mbps**（单客户端）。**本文 §3/§4 写的"单帧约 35 KB ≈ 2.8 Mbps"是估算、偏乐观**，请按实测值理解。
> - **回退看门狗的要点（重要，值得沿用）**：**不能用 `MjpegStreamClient.status` 判断** —— 它收到 HTTP 200 就置 `Streaming`，端点活着但不吐帧时照样报"正常"。实际实现按**帧的新鲜度**判：**3 秒没有新帧 → 回退订阅 `/keyframe`；又有帧 → 退订**（500 ms 轮询）。这同时覆盖"连不上"和"连上了没帧"。
> - 验收结论：进「开始作业」→ 服务端 `clients:1 / fps:10`、画面在动；离开页 → `clients:0`、手机侧 0 条 5010 连接（不烧带宽、不烧合成 CPU）；导航页视频（`?profile=video_link`）不受影响。

- 日期：2026-09-18
- 服务端：固件镜像 `slamibot_d360_firmware`（相机节点 `oak_hardware_trigger_ros` 内嵌，自 **1.0.22** 起提供，**1.0.23** 起空闲不空转）
- 客户端：`F:\SLAMIBotApp`（Kotlin / Compose，分支 `codex/native-compose-filament`）
- 背景：用户要求「彻底解决视频卡 + 坐标卡，预览拉到 10 FPS，不影响 3D 空间重建」

---

## 1. 一句话

开始作业页的预览**不再从 rosbridge 订阅 `/keyframe`**，改为拉一条**独立的 HTTP MJPEG 端点**（帧率 10 fps、带宽反而更低）。这样 rosbridge 上不再有大图，**位姿不会被队头阻塞**（就是你们当年遇到的"坐标延迟 2–3 秒"），预览也从 1 fps 提到 10 fps。

**3D 空间重建完全不受影响**：重建走 PCD；`/keyframe` 与 `oak_keyframe_stitcher` 一个字节没改（预览是从相机帧另派生的一路小图）。

---

## 2. 为什么必须换（根因）

位姿、点云、图片**全走同一条 rosbridge WebSocket**：

```
位姿(10Hz)  ┐
点云(867KB) ├─ 同一条 TCP → 一张 0.39MB 的 /keyframe 进来，后面的位姿只能排队 → 延迟 2–3s
图片(0.39MB)┘
```

把预览节流到 1 fps（`KEYFRAME_THROTTLE_RATE_MS = 1_000`）只是**降低队头阻塞的频率**，治标。**把大图搬离这条 socket 才是治本** —— 搬走之后，rosbridge 上只剩小而必要的数据，且预览视频卡了也只卡自己。

---

## 3. 新端点与协议

```
GET http://<host>:5010/api/camera/preview.mjpeg
```

- **端口 5010**（容器 `network_mode: host`，直接可达；这个端口就是当初 H.264 用过的那个，现已释放）
- **协议就是标准 MJPEG**：`Content-Type: multipart/x-mixed-replace; boundary=frame`，每帧 `--frame` + `Content-Type: image/jpeg` + `Content-Length` + JPEG 数据
  → **APP 已有的 `MjpegStreamClient` 可以直接复用**（导航页那条视频就在用它，行为一致，无需新写解析代码）
- **画面内容**：三路相机横拼（**左 | 前 | 右**），面板顺序与 `/keyframe` **完全一致**（`B, A, C`）→ **现有三格 UI 不会左右颠倒，UI 代码不用改**
- **默认规格**：每路 480×300 → 整图 **1440×300**；**10 fps**；Q70；**实测单帧 ~60 KB ≈ 4.8 Mbps**（本节早期估算的 35 KB / 2.8 Mbps 偏乐观，以实测为准）

**诊断接口**：

```
GET http://<host>:5010/api/camera/preview.mjpeg/status
```

```json
{"serving": true, "fps": 10.0, "clients": 1, "width": 1440, "height": 300, "bytes": 35210}
```

`serving: false`、端口连不上、或 3 秒内没有帧 → **按下面第 6 节回退**。

---

## 4. 收益（实测数据）

| | 现在（rosbridge `/keyframe`） | 新（独立 HTTP 预览） |
|---|---|---|
| 预览帧率 | **1 fps**（被节流） | **10 fps** |
| 预览带宽 | 0.39 MB × 1.33(base64) ≈ **4.2 Mbps** | 35 KB × 10 ≈ **2.8 Mbps** |
| 位姿 | 被大图队列阻塞（2–3 秒延迟） | **不再被阻塞** |
| 解码后 Bitmap | 5760×1200 → **27 MB** | 1440×300 → **1.7 MB**（小 16 倍，GC 抖动消失） |
| OAK 编码器 | 3 个 | **还是 3 个**（OAK 上限 5，零压力） |
| 服务端 CPU | — | ~0.25 核（**仅预览打开时**） |

**帧率提高 10 倍，带宽反而降到 2/3** —— 因为每帧小得多。

---

## 5. APP 侧要改什么

| 文件 | 改动 |
|---|---|
| `NativeDataCollectionSession.kt` | **预览改走新端点**：用 `MjpegStreamClient` 拉 `http://<host>:5010/api/camera/preview.mjpeg`，解码出的 Bitmap 继续喂给现有的 `keyframe: StateFlow<Bitmap?>` → **UI（`NativeDataCollectionScreen.kt`）一行都不用改** |
| 同上 | **停用**对 `/keyframe` 的 rosbridge 订阅（`subscribe("/keyframe", "sensor_msgs/CompressedImage", KEYFRAME_THROTTLE_RATE_MS)`）。**保留它作为回退路径**（见 §6），不要直接删掉 |
| 同上 | 顺带解决 GC 抖动：新预览只有 1440×300，不需要再纠结 `inSampleSize`；若仍想再省，`BitmapFactory.Options` 里设 `inPreferredConfig = RGB_565` 即可 |
| `RobotEndpoint.kt` | 新增预览 URL（端口 5010）。**建议命名 `collectionPreviewUrl`**（不要叫 h264Port —— H.264 那条路已经废弃了） |

**点云那条不要动**：它是 cbor-raw + `queue_length=1` 的正确用法。但有另一件事建议一起做（不在本文范围）：采集页的 `COLLECTION_THROTTLE_RATE_MS = 100`（10 Hz）配合 867 KB/帧的点云 = 建图中 **28–35 Mbps**，而预览视图只画 10,000 点 —— 服务端点云降采样能再省好几倍带宽。

---

## 6. 回退

```
连 ws/http://<host>:5010/api/camera/preview.mjpeg
  ├─ 连接失败 / 3 秒内没有帧  → 回退到 rosbridge 订阅 /keyframe（现有逻辑，保留）
  └─ 播放中断开               → 退避重连（1s/2s/4s，上限 10s），连续 3 次失败再回退
```

回退时预览会退回 1 fps 的旧行为（能用但卡），并**不影响位姿**（位姿本来就在另一条逻辑流上，只是过去被大图连累）。

---

## 7. 验收标准

1. **预览 10 fps**：`curl` 数帧率，或用 `adb logcat` 看 APP 打印的接收帧率（应 ≈10）。
2. **位姿不再延迟**：**动手建图**（不是静止），观察 APP 里坐标/点云跟随是否还有 2–3 秒滞后；同时可在设备上 `rostopic hz /amcl_pose`（导航款）或看 `/topic_frequencies` 是否稳。
   > 关键：**必须在 rosbridge 上有大图负载的场景下测**（即预览打开 + 建图中），否则测不出队头阻塞是否已消除。
3. **三格位置正确**：预览里左/前/右与 `/keyframe` 一致（面板顺序已对齐）。
4. **重建不受影响**：`/keyframe` 仍 ~4 Hz、三路 `/SLB_CAM_*/compressed` 仍 ~10 fps；建图产出的 PCD/地图与改动前一致。
5. **回归**：导航款里导航页视频（走导航容器的 `?profile=video_link`，10 fps）不受影响。

---

## 8. 不要做的事

- **不要**改 `/keyframe` 的话题、频率（`keyframe_hz`）、JPEG 质量（`jpeg_quality`）。
- **不要**动 `oak_keyframe_stitcher`。
- **不要**给 OAK 新增任何 `VideoEncoder`（上限 5 个，已用 3 个；新增会饿死某一路相机，现象是"相机已连接、publisher 存在、完全没有帧"，且 `/keyframe` 静默断流）。
- **不要**把预览再放回 rosbridge。
- 服务端参数（`~preview_fps` / `~preview_scale` / `~preview_quality` / `~preview_cam_order`）都在固件侧，需要调就找固件线，不要硬编码进 APP。
