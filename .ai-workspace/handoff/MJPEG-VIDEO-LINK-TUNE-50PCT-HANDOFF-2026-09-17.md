# 交接：把实时视频改回 MJPEG 压缩链路，压缩强度定为 50%（不用 H.264）

- 日期：2026-09-17
- 交接对象：接手改代码的 AI（**注意：本文是规格与现状，不是待办清单的执行记录**）
- 用户原话：「不使用 .h264，直接使用之前在导航控制里面实现的暴力压缩算法（图传链路），但是不用像他那样压缩 95% 画质，压缩到 50% 就行了」
- **设备当前不在手边**（用户已下班），所以本文里标注为「需上机核对」的项必须在有设备时先核对再改。

---

## 0. 一句话任务

把面向操作端的实时视频从 H.264 改回**导航服务端已有的 MJPEG 重编码链路**，并把压缩强度从「压到原来的 ~18%（实测带宽降 95.4%）」**放宽到 50%（带宽约减半）**，同时保证**空间重建链路 /keyframe 完全不受影响**。

---

## 0.1 进度快照（2026-09-17 深夜更新 —— 大部分已完成，别再重复做）

| 事项 | 状态 | 证据 |
|---|---|---|
| 导航侧压缩强度 18% → **50%** + 画质地板 | ✅ **已完成**（由 `hekawena` 实现） | 分支 `codex/mjpeg-video-link-50pct-20260917` 的 **`b4a6dfe`**，只动 `capture.py`（+41/−14）。**已逐条核对与 §3.1 规格一致**：`CAMERA_VIDEO_LINK_TARGET_RATIO` 默认 0.5 / clamp 0.2–1.0；`MAX_WIDTH` 1280 / clamp 640–1920；`JPEG_QUALITY` 80 / clamp 60–90；`FPS` 10；宽度地板 `max(960, 0.75×max_width)`、质量地板 60、到地板即停；明确只作用于 video_link 档，`/keyframe`、直通档、帧缓存、不插帧语义均未动 |
| `CAMERA_TOPIC` 默认改 **`CAM_A`**（前相机） | ✅ **已完成并已裁决保留**（由我补，用户 2026-09-17 深夜拍板） | 同一分支的 **`b6bec0d`**，只动 `ros_client.py:461`。**注意：该缓存同时供实时视频与拍照取帧，拍照来源也一并变成前相机**。裁决理由见下方「默认值取舍原则」 |
| 固件侧移除 H.264（本文件 §3.2 的**做法 B**） | ✅ **已完成**（代码层） | GitHub `kunkunwei/SLAMIBOT_D360` main **`e799f1b`**（revert 5 个提交，−994 行）。已自证 `git diff 28a2cc7 -- src/oak-camera_driver` 为空 |
| 出固件干净镜像 **1.0.21** | ⏳ **待做（需设备）** | 在 701 上 `git pull && DOCKER_BUILDKIT=0 bash docker_build.sh --push patch`，版本会自动 bump 到 1.0.21 |
| 导航镜像重建 / 部署到 715 | ⏳ **待做（需设备）** | 见下方「导航侧出货流程」 |
| 真机验收（§5 全部项） | ⏳ **待做（需设备）** | 特别是 **CPU 增量**（重编码分辨率 480→1280）与 `/keyframe` 不受影响。⚠️ 本文原先估计「Pillow 开销涨约 7 倍」是**只算缩放+编码的面积比**；离线实测（见文末「本地验证」）总耗时只涨 **1.44x**，因为全分辨率解码才是大头且新旧都要付 —— 但仍须在 Jetson 上实测 |

### 默认值取舍原则（重要，避免再走回头路）

**所有"按机型不同"的默认值，一律取新机型（715 那一代）的值**，理由（用户明确）：

- 新设备是**一键部署**、**交付客户后我们不能再随意更改** → 默认值错了就等于是把错误交给客户；
- 701 那台老机型是**开发设备**，随时可以手工改（用环境变量覆盖即可）。

因此：

| 按机型的项 | 新机型（715）取值 | 老机型（701）如何覆盖 |
|---|---|---|
| 视频链路相机（`CAMERA_TOPIC`） | `/SLB_CAM_A/compressed`（前/中间） | 环境变量 `CAMERA_TOPIC=/SLB_CAM_B/compressed` |
| `/keyframe` 拼接顺序（`oak_keyframe_stitcher` 的 `cam_topics`） | `B,A,C` = **左,前,右** ← 已是正确的从左到右顺序，**不要"顺手改"** | 老机型若要改，需单独确认（属重建红线，见 §1.2/§6） |
| H.264 链路相机（**本方案已废弃该项**） | — | — |

> 曾经有个方案是"不改代码默认值，改在设备 compose 里加 `environment:`"——**已作废**：那会让新机开箱就显示侧面相机（正是用户最初反馈的现象），而且装机脚本的升级路径只改 `image:` 行、不会自动补 `environment`，等于又回到"到处打补丁"。

### 交付模型（重要，别搞错）

**设备上的一切都是通过脚本从阿里云 ACR 拉镜像部署的**（`registry.cn-shanghai.aliyuncs.com/slamibot/...`）。因此：

- **代码推到 Git 只是开发动作，真正交付物是 ACR 上的镜像。**「改完了」不等于「能部署了」，必须 `docker push` 到 ACR。
- **Gitee 仓库不在部署链路上**（用户已明确：暂时不动）。Gitee 上的固件镜像停在 1.0.15、导航镜像未同步，**但这不影响交付** —— 别被它带偏，也不要按它拉基线。开发基线一律用 GitHub `kunkunwei/*`。

### 导航侧出货流程（`d360_nav2d`）

1. **构建 arm64 镜像**。仓库里有 `scripts/build_product_image.ps1`（Windows/pwsh，`docker build --platform linux/arm64 -f Dockerfile.product`）与 `scripts/export_product_image.ps1`（`docker save` 成 tar.gz）。**注意两点**：
   - 这两个脚本**都没有 push 到 ACR 的步骤**，推送是手工的；
   - 历史记录显示 **Windows/QEMU 构建失败过**，后来改用 **Jetson 原生 aarch64 构建**。**1.2.3 实际是怎么构建并推上去的，需向维护者确认**（本文不猜）。
2. **打 tag 并推 ACR**：`registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d:<新版本>`。当前部署的是 **`1.2.3`**，本次改动应出新版本（如 `1.2.4`），**不要覆盖 1.2.3**（回滚要用）。
3. **改装机脚本里的默认镜像**：`scripts/install_2d_nav.sh` 与 `d360_deploy/nav2d/install_2d_nav.sh` 里 `IMAGE=` 的默认值目前都硬编码为 `d360_nav2d:1.2.3`，**两处都要改成新 tag**，否则一键装机装的还是旧镜像。
4. **设备上部署**：跑装机脚本（或按现有 compose 流程改 `scout-nav` 的 image tag 后 `docker compose up -d scout-nav`）。

### 固件侧出货流程（`slamibot_d360_firmware`）

`docker_build.sh --push patch` 一步到位：编译 → 自动 bump 版本号 → commit → `docker build` → `docker push` 到 ACR。本次从 `e799f1b` 构建即为 **1.0.21**，功能 = 1.0.17 的固件（无 H.264）。

> 小坑：`docker_build.sh` 里那步 `git push origin` 在 701 上会失败（`origin` 指向一个不存在的仓库），脚本会**静默跳过**（打印 warning 后 return 0）——所以**版本号提交不会自动进 Git**，需要事后手工 `git push cloud main`（`cloud` 才是可用的 GitHub remote）。

---

## 1. 现状：机器人上有两条互不相干的视频路径

### 1.1 面向操作端（APP / WEB 看的画面）

| 路径 | 端点 | 实现位置 | 实测（2026-09-17，715） |
|---|---|---|---|
| **A. H.264 WebSocket（本次要废弃的）** | `ws://<host>:5010/api/camera/stream.h264` | 固件仓库 `src/oak-camera_driver/scripts/oak_hardware_trigger_ros.py`（OAK 硬编 + 内嵌 WS 服务 + 自适应切档） | 全分辨率 1920×1200、10 fps；快链路 10.02 Mbps，办公 Wi-Fi 上自动退到 3 Mbps |
| **B. MJPEG HTTP（本次要用的）** | `http://<host>:5000/api/camera/stream.mjpeg` | **导航仓库** `src/nav_api/fastapi_service/capture.py` | 默认档：1920×1200 原图直通、8 fps、**20–23 Mbps**；`?profile=video_link`：**0.955 Mbps**（较 20.81 Mbps 降 **95.4%**）、10 fps |

### 1.2 数据采集 / 空间重建（**红线，不能动**）

`oak_keyframe_stitcher` 订阅三路 `/SLB_CAM_*/compressed`（OAK 原生 **MJPEG Q90**），横拼成 1920×5760 的 `/keyframe`（~4 Hz），APP 拿它做建图与 3D 重建。

> **关键**：MJPEG Q90 单帧约 **2.47 Mbit**。任何"降低相机端 MJPEG 质量"的做法都会直接损伤重建输入，**一律禁止**。压缩只能发生在视频链路的下游（即 `capture.py` 里对 video_link 档的重编码），这样重建链路一个字节都不变。

### 1.3 硬件事实（决定上限，不要再试图突破）

- 相机出图被 STM32 硬触发锁死在 **10.000 fps**（`F:\slamibot_stm32\USER\main.c:49` `TIM2_PWM_Init(999, 7199)`）。代码里出现的 20 fps 都是配置值、会被硬触发覆盖。**视频永远只有 10 fps**。
- **OAK 同时最多 5 个视频编码器**。三路相机各占一个 MJPEG（供 /keyframe），只剩 **2 个余量**给视频链路 → 这也是 H.264 方案最多只能 2 档的根本原因。

---

## 2. 要改成什么（决策）

1. **停用 H.264 链路**（视觉上等价于"回到 MJPEG"）。
2. **保留** `capture.py` 里那套「服务端解码 → 按目标字节数重编码 → 逐级降分辨率」的暴力压缩机制，**只放宽强度**：
   - 压缩比从 `0.18` 改为 **`0.5`**（目标字节 = 原始 JPEG 的 50%）。
   - 同时把分辨率/质量的下限抬高，**不许再掉到 480px/Q20 那种糊画面**。
3. **不要**用"降低 OAK 相机端 MJPEG 质量"来省带宽（会损伤重建，见 §1.2）。

---

## 3. 改动清单（按仓库分）

### 3.1 导航仓库 `d360_nav2D` ／ 远端 Gitee `electech6/d360_nav2D` —— **主改动**

**要改的文件**：`src/nav_api/fastapi_service/capture.py`

> ⚠️ **需上机核对**：本地克隆在分支 `codex/video-link-stream-20260904`，而设备上跑的是镜像 `d360_nav2d:1.2.3`。本文给的行号来自本地克隆，**改动前必须以部署版为准**：
> ```
> docker exec scout-nav bash -lc 'find /Scout_mini_navigation -name capture.py'
> docker exec scout-nav bash -lc 'grep -n "target_ratio\|MAX_WIDTH\|JPEG_QUALITY\|VIDEO_LINK_FPS\|CAMERA_STREAM_FPS" <上一步找到的路径>'
> ```
> 本地克隆里相关位置：`capture.py:48-52`（参数）、`:75`（target_ratio）、`:102`（逐级降分辨率）、`:366-379`（_mjpeg_frames）。

#### (a) 压缩强度：`target_ratio` 0.18 → 0.5，并**改成环境变量**

本地克隆 `capture.py:75`：

```python
target_ratio = 0.18
target_bytes = max(1024, int(len(frame) * target_ratio))
```

改成可现场调整（用户反复要求"参数改动不要重建镜像"）：

```python
target_ratio = _bounded_env_float("CAMERA_VIDEO_LINK_TARGET_RATIO", 0.5, 0.2, 1.0)
```

> 保留一个下限 0.2 是为了防止有人把它调成 0.05 再现"糊成一团"。上限 1.0 = 不压。

#### (b) 默认参数放宽

本地克隆 `capture.py:48-52`：

| 环境变量 | 现在默认 | 现在允许范围 | **改成默认** | **改成范围** |
|---|---|---|---|---|
| `CAMERA_VIDEO_LINK_FPS` | 20.0 | 1.0–20.0 | **10.0** | 1.0–20.0（不变） |
| `CAMERA_VIDEO_LINK_MAX_WIDTH` | 480 | **160–1280** | **1280** | **640–1920** |
| `CAMERA_VIDEO_LINK_JPEG_QUALITY` | 40 | **20–85** | **80** | **60–90** |

说明：
- `FPS` 默认写 20 是历史遗留（源流本来就 10 fps），改成 10 语义更准，行为不变。
- `MAX_WIDTH` / `JPEG_QUALITY` 的**上界也必须放宽**（现在是 1280 / 85），否则想"全分辨率不缩放"时会被 clamp 卡住。
- `JPEG_QUALITY` 的下界从 20 抬到 60，**这本身就是画质下限的一道保险**。

#### (c) 逐级降分辨率要有地板（本地克隆 `:102`）

现在的逻辑会一直降到能塞进 `target_bytes` 为止（历史实测最低到过 160px/Q20）。按用户"不要 95%、50% 就够"的要求，加地板：

- 最低宽度不小于 **960**（或用 `MAX_WIDTH * 0.75`，取更大者）；
- 最低 JPEG 质量不小于 **60**；
- **触到地板就停止继续降级**，宁可偶尔掉帧/超一点预算，也不要再牺牲画质。超预算时保留现有 `LOGGER.warning`（`:110`）便于观测。

#### (d) 保持不动的部分（很重要）

- `_mjpeg_frames()`（`:366-385`）**"只在收到新帧才发、不插帧"** 的语义必须保留 —— 这是避免延迟累积的关键。
- 非 video_link 档的**原图直通**行为不要改（APP 的默认档走的是这个）。
- 缓存机制 `_STREAM_CACHE` / `_STREAM_ENCODE_LOCK`（`:35-37`）保留，别为了省事去掉，否则多客户端会重复编码放大 CPU。

### 3.2 固件仓库 —— **关掉 H.264**（代码可改可不改）

#### ⚠️ 先搞清楚在哪拉代码（这里有个坑）

| 位置 | 状态 | 说明 |
|---|---|---|
| **GitHub `git@github.com:kunkunwei/SLAMIBOT_D360.git`** | ✅ **唯一权威、最新**（`main` = `afe4155`） | 所有版本号提交都推到这里 |
| Gitee `https://gitee.com/electech6/SLAMIBOT_D360_Framework.git` | ❌ **停在 `1.0.15`（`2924202`）** | 比本地克隆还老，**不要用它当基线**（会同时丢掉 1.0.16/1.0.17 的串口健壮性修复和 H.264） |
| 用户本地 `F:\SLAMIBOT_D360_Framework` | ⚠️ 停在 **`1.0.17`（`28a2cc7`）**，工作树干净，远端指向 GitHub | 拉取后即为最新 |

**`28a2cc7`(1.0.17) → `afe4155`(1.0.20+) 之间只有 9 个提交，只动 5 个文件，全部在 OAK 相机驱动包里**：

```
src/oak-camera_driver/scripts/oak_hardware_trigger_ros.py   (+833)  ← H.264 全部实现
src/oak-camera_driver/scripts/oak_h264_probe.py             (新增)
src/oak-camera_driver/CMakeLists.txt / setup.py             (注册 probe)
src/device_service/src/device_basic_service.py              (版本号 1.0.18/19/20)
```

即：**固件侧自 1.0.17 起的唯一功能变更就是 H.264 视频链路本身**，别处一行没动。所以「不使用 H.264」这件事在固件侧是个**收敛动作**，不是新开发。

#### 做法 A（最快，设备上生效，不改代码）：配置关闭

设备上把 `/etc/slamibot/video_link.json` 改成：

```json
{"enable": false}
```

然后 `docker restart firmware-sensors`。相机节点只建 3 个 MJPEG 编码器（资源占用回到 1.0.17 水平），5010 不再监听。

> 注意：代码里 `enable` 的默认值从 `cc466e1` 起已经是 `False`，所以**删掉这个文件也一样是关闭**；显式写 `{"enable": false}` 只是为了日志里能看清意图（配置存在但缺 `enable` 时节点会 logwarn 报出生效值）。

#### 做法 B（**推荐**，出货用干净镜像）：把 H.264 相关提交回退后重建

留着 800 多行不会有人维护的死代码 + 一个多余端口，对出货版本是负担。用 Git 回退（历史仍在，可随时恢复）：

```bash
git checkout main && git pull            # 到 afe4155
git revert --no-commit 054c0ee 08933f4 5e9c510 cc466e1 afe4155
# 保留版本号提交 1debceb/30a2e9c（或一并回退后重新 bump 到 1.0.21）
git commit -m "revert(video-link): 移除 H.264 视频链路，改由导航侧 MJPEG 压缩承担"
```

回退后 `src/oak-camera_driver/**` 应与 `28a2cc7` 一致（可用 `git diff 28a2cc7 -- src/oak-camera_driver` 自证为空）。随后正常 `docker_build.sh --push patch` 出 1.0.21。

> 无论 A 还是 B，**APP 侧都不需要改**（见 §3.3）。

#### 固件侧**不需要改**的部分（重点澄清一个误解）

用户提到「之前好像还改了开始作业的数据采集那一部分，虽然改成什么 5010 端口了」——**这两个是两回事，数据采集跟 5010 无关**：

| 功能 | 走的通道 | 固件侧相关代码 | 本次是否要改 |
|---|---|---|---|
| **实时视频**（APP 导航页画面） | **5010** WebSocket（H.264）→ 本次废弃后改走 `:5000/api/camera/stream.mjpeg` | `oak_hardware_trigger_ros.py` 的 H.264 段 | **要**（关掉/回退） |
| **数据采集 / 开始作业**（建图关键帧、3D 点云） | **rosbridge `:9090`** + `/keyframe` + `/global_cloud_navigation` | `oak_keyframe_stitcher.py`（发布 `/keyframe`）、`rosbridge_patch/*` + `Dockerfile:8-21`（cbor-raw 补丁，**新设备看不到 3D 点云就是靠它修的**）、OAK 三路 MJPEG Q90 | **不改** |

- 全仓库里 `5010` **只出现 1 次**（`oak_hardware_trigger_ros.py:426`），可自行验证：`grep -rn 5010 .`。
- `rosbridge_patch/` 那三个文件 + Dockerfile 里那段 `ROSBRIDGE_PATCH_OK` 断言，就是用户记忆中「改过开始作业数据采集」的那处改动（提交 `60560bb`，**你的本地克隆 1.0.17 里已经有了**，也已在 715 的镜像里）。
- 该链路是**空间重建的输入**，属红线，见 §1.2 与 §6。


### 3.3 APP `SLAMIBotApp` —— **本次不需要改**

APP 侧已经实现了完整回退链，只要 5010 不再监听就会自动回到 MJPEG，链路如下（供核对）：

- `H264StreamClient.runConnectionLoop()` → `connectOnce()` 失败（5010 无监听，TCP 快速拒绝）→ 因为 `streamedOnce == false` → `onGiveUp()`
- `NativeNavigationSession.fallbackToMjpeg()` → 请求 `endpoint.videoLinkCameraStreamUrl`
- `RobotEndpoint.videoLinkCameraStreamUrl` = `"$cameraStreamUrl?profile=video_link"` = `http://<host>:5000/api/camera/stream.mjpeg?profile=video_link`

**可选清理**（降低复杂度，非必做）：删掉 `H264StreamClient.kt` / `H264StreamView.kt` / `H264AnnexB.kt` 与 `RobotEndpoint.h264Port`，视频卡直接走 MJPEG。**但不要动 `MjpegStreamClient` / `MjpegStreamView`**（回退依赖它们）。

---

## 4. 「50%」的确切定义与标定数据

**定义**：`target_ratio = 0.5`，即**重编码后的 JPEG 字节数目标 = 原始帧字节数的 50%**，对应面向操作端的带宽从 **20–23 Mbps 减到约 10–11 Mbps**。

**标定参考（真机实测，1920×1200 @10 fps）**：

| 编码 | 单帧大小 | 说明 |
|---|---|---|
| MJPEG Q90（OAK 原图，重建用） | **2.47 Mbit**（≈309 KB） | 基线，`/keyframe` 的输入，**不可动** |
| MJPEG Q50 | **1.22 Mbit**（≈152 KB，约为 Q90 的 35%） | 台架 59 fps 实测换算 |
| MJPEG Q90 单路 @10 fps | **24.72 Mbps** | 台架实测 |

→ 结论：**"压缩到 50%" 大约相当于 全分辨率下 JPEG 质量降到 Q65–Q70**，画面清晰度损失很小。若配合 `MAX_WIDTH=1280`，可以在更低 CPU 下拿到同样的 50% 目标。

**压缩强度对照**（同一个旋钮，供你判断改动幅度）：

| 设置 | 面向操作端带宽 | 画质 |
|---|---|---|
| 现状（`target_ratio=0.18`，480px/Q40） | 0.955 Mbps（降 95.4%） | 糊（用户明确不接受） |
| **目标（`target_ratio=0.5`，1280px/Q80）** | **约 10 Mbps** | 接近清晰 |
| 不压缩（`target_ratio=1.0`，原图直通） | 20–23 Mbps | 最好，但弱网会拥塞 |

---

## 5. 验收标准（必测项）

1. **带宽**：`?profile=video_link` 在稳定场景下实测 **≈ 原始档的 50%**（用 §7 的量测脚本；原始档先测一遍做基线）。
2. **帧率**：**10 fps**（源流上限），且与原始档一致，**不允许因为重编码掉帧**。
3. **画质**：人工对比 1920×1200 原图档与 video_link 档，**不允许出现 480px 时代那种明显糊/方块**；分辨率不低于 960px 宽。
4. **重建不受影响（红线）**：`/keyframe` 仍为 ~4 Hz、仍是三路 MJPEG Q90 合成；`/SLB_CAM_*/compressed` 质量参数**未被修改**；建图前后画面/点云正常。
5. **CPU（本次最大风险）**：重编码分辨率从 480px 提到 1280–1920px，Pillow 解码+编码的 CPU 会**涨约 7–16 倍**。必须在真机上测：
   - `docker stats scout-nav --no-stream` 与容器内 top，确认 FAST-LIO（`laserMapping`）与导航不受影响；
   - 若 CPU 吃紧，优先降 `MAX_WIDTH`（1280 → 1024 → 960），**不要降 JPEG 质量下限**。
6. **弱网行为**：在办公 Wi-Fi 这类弱链路上，允许掉帧，但**不允许画面退回糊状**（这是本次改动与旧行为的核心区别）。
7. **APP 端**：打开导航页视频，能出画、无报错；`adb logcat -s H264Stream` 应能看到一次快速失败并回退（或清理 H.264 客户端后完全无该日志）。

---

## 6. 红线：绝对不要做的事

1. **不要改 OAK 相机端的 MJPEG 质量**（`oak_hardware_trigger_ros.py` 里 `setQuality(90)`）—— 会直接损伤 `/keyframe` 与 3D 重建。
2. **不要动 `oak_keyframe_stitcher.py`** 及其话题顺序（`B, A, C`）与参数（`keyframe_hz 5.0`、`jpeg_quality 50`）。
3. **不要把压缩放到相机端**或用"再开一个编码器"的办法 —— OAK 只有 5 个编码器余量，已经用满 5 个中的 3 个，任何新增都会饿死一路相机（现象是"相机已连接、publisher 存在、完全没有帧"，且 `/keyframe` 静默断流）。
4. **不要为了省 CPU 把 `_mjpeg_frames()` 改成固定频率插帧** —— 会造成延迟累积（历史上"坐标滞后"就与这类队头阻塞有关）。
5. **不要在 `core` 容器上做任何重建** —— `rosmaster` 跑在 `core` 里，重建 `core` 等于重启整机 ROS master，之后**必须** `docker restart scout-nav`，否则导航栈与底盘会"看着在线、实际脱管"（本次已踩过，现象是"底盘激活显示 none"）。
6. 这台设备上**跨容器的 `rostopic hz` 不可信**：`scout_msgs` 只在 `scout-nav` 里、`livox_ros_driver2/CustomMsg` 在 `core` 里加载不了，会误报 NO_DATA。**权威视角是 `/topic_frequencies`**。
7. 服务端相机节点日志在 `/root/.ros/log/latest/oak_hardware_trigger_ros*.log`，**不在 `docker logs`**。

---

## 7. 量测脚本（现成的，直接用）

`F:\slamibot_agent\tmp\mjpeg_measure.py`（纯标准库，无需装依赖）：

```
python tmp/mjpeg_measure.py "http://<host>:5000/api/camera/stream.mjpeg"              10
python tmp/mjpeg_measure.py "http://<host>:5000/api/camera/stream.mjpeg?profile=video_link" 10
```

输出 `Mbps` / `jpeg_frames` / `fps` / `avg_frame_kB`，正好对应 §5 的验收项 1–2。**先测原始档做基线，再测 video_link 档**。

---

## 8. 需上机核对的清单（因为写本文时设备不在手边）

1. 部署镜像 `d360_nav2d:1.2.3` 里 `capture.py` 的**真实路径与行号**，以及 §3.1 的参数名是否与本文一致（本地克隆是另一个分支）。
2. 部署版的 `target_ratio` 当前实际值（可能已被环境变量覆盖）。
3. 容器实际注入的环境变量：`docker exec scout-nav bash -lc 'env | grep -i CAMERA'`。
4. 原始档 / video_link 档的**当前实测带宽基线**（用 §7 脚本，改动前后各测一次）。
5. 重编码的 CPU 占用基线（改动前先测，否则改动后无法判断增量）。
6. 715 与 701 的相机物理布局不同（**715 = `CAM_A` 前(中间) / `CAM_B` 左 / `CAM_C` 右**；701 老机型沿用 `CAM_B`）。注意 `capture.py` 的 `CAMERA_TOPIC` 环境变量（本地克隆默认 `/SLB_CAM_B/compressed`）—— **715 上应确认它指向 `CAM_A`**，否则 APP 看到的是侧面画面。

---

## 9. 回滚

- 导航仓库：改动集中在 `capture.py` 一个文件，且新旋钮是环境变量 → **回滚只需把 `CAMERA_VIDEO_LINK_TARGET_RATIO` 调回 0.18 / 或 `git checkout -- capture.py` 重建**。环境变量能覆盖时甚至不用重建镜像。
- 固件：`/etc/slamibot/video_link.json` 改回 `{"enable": true, "camera": "CAM_A", "tiers_kbps": [10000, 3000]}` + `docker restart firmware-sensors` 即可恢复 H.264（代码仍在，默认关闭）。
- 不建议删除 H.264 代码，除非用户明确要求 —— 保留可回滚。

---

## 附：本次交接**不需要**改的东西（避免多余动作）

- APP 的回退逻辑（已完备）。
- OAK 相机节点、keyframe 拼接节点、任何 ROS 话题/消息定义。
- 底盘、导航栈、ROS master 相关的一切。
- 5010 端口本身：H.264 关掉后自然不再监听，无需改代码或端口分配。

---

## 执行结果（2026-09-17 深夜，接手 AI 追加；本节取代 §8 的部分「需上机核对」）

> **本节在 2026-09-17 深夜被二次修订**：初版写于用户裁决之前，曾主张「不改 `CAMERA_TOPIC` 代码默认值」并记「做法 B 未执行」——**这两条都已被推翻**，下面为最终状态。

### 交付（最终状态）

- **分支**：`codex/mjpeg-video-link-50pct-20260917` @ **`b6bec0d`**（GitHub `kunkunwei/Scout_mini_navigation`；**未合并 master**，按 protected-branch 规则只推 `codex/*`）。该分支含 **2 个文件**：
  - `src/nav_api/fastapi_service/capture.py`（`b4a6dfe`，+41/−14）—— §3.1 的全部改动（(a)(b)(c) 全做，(d) 全保留）。
  - `src/nav_api/fastapi_service/ros_client.py`（`b6bec0d`，1 行）—— `CAMERA_TOPIC` 默认 `CAM_B` → **`CAM_A`**，见下「最终裁决」。
- 构建：`git fetch && git checkout codex/mjpeg-video-link-50pct-20260917`，正常走 `Dockerfile.product`。**交付物是 ACR 镜像**（见 §0.1「交付模型」）。
  若要直接用 master：`git push kunkunwei codex/mjpeg-video-link-50pct-20260917:master`（快进、无合并提交，**需自行决定**）。

### §8「需上机核对」的源码级答案（1/2/6）

| # | 项 | 结论 |
|---|---|---|
| 1 | 部署版路径/行号 | 源码 `src/nav_api/fastapi_service/capture.py`；镜像内 `/Scout_mini_navigation/install/lib/python3/dist-packages/fastapi_service/capture.py`（runtime 阶段只 COPY `install/`，不带 `src/`）。行号与 §3.1 完全一致 |
| 2 | 部署版 `target_ratio` | `0.18` 写死。**证据**：`kunkunwei/master`(1ad7809) 的该文件 blob == 改前本地文件 == `bb2fe15`；1.2.3 = 1.2 全量构建 + 1.2.1（4 个 .py）→1.2.2/1.2.3（仅地图清理）三层 overlay，**overlay 从未碰过 capture.py** |
| 6 | `CAMERA_TOPIC` | 原默认 `/SLB_CAM_B/compressed`；**已改默认值为 `CAM_A`**（`b6bec0d`），理由见下 |

### §3.1 的一个修正：**没有**需要一起改的测试文件

`test_camera_stream_profile.py` 是 `5ad6000` 加的，**没有进 master**（`git ls-tree kunkunwei/master:src/nav_api/tests/` 里没有它）。所以本次改动**不会让任何现有测试变红**，也没有测试要同步更新。该测试文件本身把旧契约写死（`(20.0, 160, 85)`、宽度 480、体积 ≤20%），**若要**把它捡回来，必须按新契约重写（期望值 `(20.0, 640, 90)`、宽度 640、体积上限 0.5、并断言降级不会低于 960px）。

### CAMERA_TOPIC：最终裁决 = 代码默认改 `CAM_A`（`b6bec0d`）

> 初版本节主张「不改代码默认值、改在 715 的 compose 里加 `environment`」。**该方案已作废，勿再执行 compose 那套命令**（新设备上根本带不上，理由见下）。

**用户裁决（2026-09-17 深夜）**：保留 `b6bec0d`，代码默认按新机型取 `CAM_A`。理由：**新设备是一键部署、交付客户后我们不能再随意更改，默认值错了等于把错误交给客户；701 是开发设备，随时可手工改**（需要时用环境变量 `CAMERA_TOPIC=/SLB_CAM_B/compressed` 覆盖）。

compose 方案作废的直接原因：`install_2d_nav.sh` 的**升级路径只改 `image:` 一行、不动其它内容**，所以「在 compose 里加 environment」在新设备上不会被脚本带上，等于又变成到处打补丁。

**副作用（用户已知并接受）**：该帧缓存同时供**实时视频**与**拍照取帧**（相册 + 到点自动拍照），所以拍照来源也一并变成前相机。

⚠️ **由此推广到所有按机型的默认值：一律取新机型。** 已核对 `oak_keyframe_stitcher` 的 `cam_topics` 顺序 `B,A,C` = 左,前,右，对新机型已是正确的从左到右顺序，**不要"顺手改"**（重建红线）。

715 上机时仍建议核一遍环境变量（残留的 `CAMERA_VIDEO_LINK_*` 会**覆盖代码默认值**；残留的 `CAMERA_TOPIC` 说明有旧配置要清）：

```bash
docker exec scout-nav env | grep -i CAMERA
```

### 本地验证（真机验收仍按 §5 全部保留）

- `py_compile` + 离线真实 Pillow 复算：`tmp/mjpeg-verify/verify_video_link_ladder.py`（打桩 fastapi/pydantic/nav_api 依赖，按路径加载**真实** `capture.py`，不复制逻辑；Pillow 装在 `tmp/mjpeg-verify/pylibs`）。
- 合成 1920×1200 源帧（校准到 Q90 ≈ 309 KB，对齐 §4 标定）：

| 设置 | 单帧 | 占源帧 | 宽度 |
|---|---|---|---|
| 旧 0.18 / 480px / Q40 | 6.5 KB | 2.1% | 480 |
| **新默认 0.5 / 1280px / Q80** | **50.4 KB** | **15.9%** | 1280 |
| 0.5 / 1920px / Q80（全分辨率） | 93.0 KB | 29.4% | 1628* |
| 0.5 / 1024px / Q80 | 32.1 KB | 10.1% | 1024 |

\* 全分辨率档触发了降级：`encode(1920, Q80)` ≈ 220 KB 超过 50% 上限（158 KB），阶梯按面积比降到 **1628** 后落到 93 KB 即停（地板 1440 未触及）。也就是说 **`TARGET_RATIO=0.5` 在这一档才真正起约束作用**。

- **地板生效证明**：高熵源图 + `TARGET_RATIO=0.2` + `MAX_WIDTH=1920` → 降级后宽度 **1440**（= `max(960, 0.75*1920)`）后停止；旧代码会一路降到 **160px/Q20**。
- **CPU**：编码耗时 18.1 ms → 26.0 ms（**1.44x**，本机）。原因是**新旧都付全分辨率 1920×1200 JPEG 解码**，增量只是 resize+encode。**远低于**本文原先估计的 7–16x，但仍必须在 Jetson 上实测（§5.5）。
- **注意（重要，供判断 50% 目标是否够）**：`target_ratio` 是**上限而非目标**——默认 1280/Q80 实测只用到源帧的 15.9%，**远低于 50% 上限**，所以默认档每帧只编码 **1 次**（CPU 友好），实际带宽会明显低于 §4 估计的「约 10 Mbps」。真机基线是旧档 0.955 Mbps / 单帧 ~11 KB，按本次 7.7x 的字节比外推，**新默认档约 7–8 Mbps**，恰好落在办公 Wi-Fi 吃得住的区间（checkpoint：10 Mbps 的 H.264 tier0 曾把 Wi-Fi 打爆并静默丢帧）。若要更接近 10 Mbps，把 `CAMERA_VIDEO_LINK_MAX_WIDTH` 调到 1920 即可（不用重建）。
- **未验证**：仓库 pytest（本机缺 fastapi/roslibpy/open3d；镜像 install-only 不带 tests）、真机带宽/帧率/CPU/画质、弱网行为。§5 七项验收**全部**留给上机。

### 固件侧现状（**做法 B 已执行**，本节取代初版「本次未改任何固件代码」）

- **GitHub `kunkunwei/SLAMIBOT_D360` main 已是 `e799f1b`**（`revert(video-link): 移除 H.264 视频链路，改由导航侧 MJPEG 压缩承担`，4 文件 / +3 −994）—— 即 §3.2 的**做法 B 已在代码层执行完毕**。原 `afe4155` 及之前 4 个 H.264 提交仍在历史里，可随时恢复。
- **独立自证（本次复核，不是转述）**：`git diff 28a2cc7 origin/main -- src/oak-camera_driver` **为空**；OAK 包里 `git grep 'ws_port|h264'` **无命中**（5010 与 H.264 代码都消失）；`28a2cc7 → e799f1b` 整体只差 `src/device_service/src/device_basic_service.py` 的版本号 3 行。→ **代码已精确回到 1.0.17 状态**，相机回到 3 路 MJPEG，编码器占用回到安全区。
- 背景（为什么 revert 是对的）：`28a2cc7 → afe4155` 那 9 个提交只动 5 个文件、**全部在 OAK 驱动包**（`oak_hardware_trigger_ros.py` +833、`oak_h264_probe.py` 新增、`CMakeLists.txt`/`setup.py` 注册、`device_basic_service.py` 版本号）→ **固件侧自 1.0.17 起唯一的功能变更就是 H.264 本身**，所以这是个纯收敛动作。
- `5010` 原先的唯一实现位置（**现已随 revert 删除**，留作档案）：`src/oak-camera_driver/scripts/oak_hardware_trigger_ros.py:426`（`H264_DEFAULTS["ws_port"]`；`config_path` = `/etc/slamibot/video_link.json`）。715 上那个 `/etc/slamibot/video_link.json` 换新镜像后成为**无效文件，可删**。
- **「开始作业的数据采集」与 5010 无关**（本次再次确认）：走 rosbridge `:9090` + `/keyframe` + `rosbridge_patch/`（`60560bb`，本地 1.0.17 已含，**revert 未触碰它**），属空间重建红线，**不改**。
- 待做：从 `e799f1b` **构建并推 ACR 出 1.0.21**（见 §0.1「固件侧出货流程」）。**做法 A（设备侧改 `video_link.json` + 重启）已不再需要**，因为代码层已经没有 H.264 了。

### 顺手发现（未修，属另一仓库）

`tmp/d360_deploy/nav2d/install_2d_nav.sh`（Gitee `electech6/d360_deploy` master）**第 1 行是孤立文本 `205`**，位于 `#!/usr/bin/env bash` 之前 → bash 会打印 `205: command not found`；因 `set -euo pipefail` 在其后，**不致命**但应删掉那一行。
