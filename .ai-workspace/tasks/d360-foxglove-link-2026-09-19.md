# TASK-2026-09-19-D360-FOXGLOVE-LINK：D360 前后端链路换 Foxglove 二进制（ROS1）

- status: **code_pushed_cloud / hardware_verification_pending**（代码已改完并推云端，未部署、未真机验证）
- technology: ROS1 Noetic（D360 现状）；不是 ROS2 迁移任务
- migration: false（D360 侧维持 ROS1；仅客户端链路协议替换）
- requester: 用户 2026-09-19（下班后）布置；要求「代码简洁、不产生多余端口、不写防御性冗余代码」

## 1. 目标

把 D360（ROS1 产品线）客户端链路从「rosbridge JSON + 手改 cbor-raw 补丁」换成 **Foxglove WS 二进制（ROS1 桥的 `ros1` 编码）**，
与 D360S（Foxglove + CDR）共用同一套前端封装，为后续「一个 APP 同时兼容 D360 / D360S」打底；同时压掉 JSON 与视频流开销；
并保证**基础款（3D 空间重建）与 2D 导航加装之间零新增依赖**。

## 2. 云端 / 本地核对（2026-09-19）

| 仓库 | 结论 |
|---|---|
| `F:\SLAMIBOT_D360_Framework`（D360 固件 ROS1，github kunkunwei/SLAMIBOT_D360） | 本地原为 `28a2cc7`(1.0.17) → 已 `fetch` + `merge --ff-only` 到 **`87c966f`(1.0.23)**；本次新进 5 个提交，1.0.17→1.0.23 共 15 个提交但净改动仅 2 文件 +531/-4（1.0.18–1.0.20 的 H.264 视频链路被 `e799f1b` 整体 revert，真正留下的是 `d07dcfa`/`e52dafa` 的「相机节点内置 HTTP MJPEG 预览」） |
| `F:\SLAMIBOT_D360_Framework_ros2`（D360S ROS2） | `codex/d360s-foxglove-cbor` = `8e83f1c` = 云端，无需同步 |
| `F:\d360_nav2D`（导航，双远端） | 三条线互不为祖先；按用户指令「以最新提交作为权威分支」取 **`4e13055`**（2026-09-18 09:14，现亦为 kunkunwei/master） |
| `F:\SLAMIBotApp`（APP） | 与云端一致；**本轮不改**（用户明确后续单独改） |

## 3. 交付（两个仓、两个分支，均已推云端）

### 3.1 固件仓 `F:\SLAMIBOT_D360_Framework` → 分支 `codex/d360-foxglove-link-20260919`（`a7037a7` + `5b22847`）

- `src/device_service/launch/core.launch`：rosbridge include → `<include file="$(find foxglove_bridge)/launch/foxglove_bridge.launch"><arg name="port" value="9090"/></include>`（**同端口 9090，无第二端口、无开关、无双桥并存**）
- `Dockerfile`：删 rosbridge 补丁层（3 COPY + 断言），新增 `ros-noetic-foxglove-bridge` 安装层
- 删 `rosbridge_patch/`（`subscribe.py` / `cbor_conversion.py` / `outgoing_message.py`，共 449 行）
- 新增 `tools/foxglove-shim/`（ROS1 版，源自 D360S 仓的 551 行 shim；**只改 3 处**：`MessageReader` 换成 `@foxglove/rosmsg-serialization`、通道判定 `encoding === "ros1"`、`parse(schema, { ros2: false })`，并删掉 CDR 时代的 `for (const ros2 of [true,false])` 兜底循环）
- 产物 `ota_server/web_page/static/modules/foxglove-roslib.js`（78,887 B）入库；删 `roslib.min.js`
- `static/main.js`：`/keyframe` 改二进制 `Blob`（删 base64 data-URL 拼接）；`/project_image` 只留字节数组路径
- 收尾提交：`.gitignore` 放行 `tools/foxglove-shim/package.json`/lock（原被全局忽略，否则改动会被静默吞掉）、`.dockerignore` 排除 `tools/`、`.codex/AGENTS.md`/`.claude/CLAUDE.md`/`docs/OTA.md`/`ota_server/setting_server.py` 的 roslibjs/rosbridge 表述同步为 Foxglove
- **未动**：`project_control.launch`（用户要求保留、上机测试后再定去留）、`docker-compose.yml`、`sensors.launch`、设备

### 3.2 导航仓 `F:\d360_nav2D` → worktree `F:\d360_nav2D-foxglove`，分支 `codex/foxglove-link-20260919`（`720a5fc`）

- `frontend/vendor/foxglove-roslib/index.js`：**vendored 单文件 shim**（源 `SLAMIBOT_D360@5b22847`，文件头写明来源与重新 vendor 方法）
  - **submodule 方案已废弃**：会把整个固件仓（72MB）塞进前端目录，且会让 `.github/workflows/publish-navigation-ui.yml`（`actions/checkout` 未开 submodules）与 `Dockerfile*`（`COPY frontend/`）直接构建失败
- `frontend/src/ros/rosClient.ts`：roslib → shim；**删掉无调用方的 `publish()`**（grep 确认唯一匹配是定义自身）；`compression`/`queueLength` 参数保留但不再下传（注释说明原因），`throttle_rate` 仍生效
- `frontend/src/runtime/config.ts`：默认连接改 **`ws://${location.hostname}:9090`**（直连桥）
- `frontend/deploy/nginx.conf`：删掉 `/rosbridge` 代理段（改直连后全仓无使用者）；`vite.config.ts` 同步删掉 dev 代理与仅因 submodule 存在的 test exclude
- `frontend/package.json`：加 `@foxglove/rosmsg`/`rosmsg-serialization`/`ws-protocol`；移除 `roslib` 与 `@types/roslib`
- 新增 `frontend/src/ros/foxglove-roslib-shim.d.ts`（25 行，只声明 SPA 实际用到的成员；shim 是无类型的 JS）
- **未动**：`src/nav_api/`、`Dockerfile*`、`docker-entrypoint.sh`、`script/`、地图与数据库；`F:\d360_nav2D` 与 `tmp/nav-50pct` 两个既有 worktree 未被触碰

## 4. 验证（主代理亲跑）

- 固件仓 shim：`npm test` → **8 checks passed**（订阅/CDR→ROS1 解码/原始 JPEG 字节/服务往返/未知服务/参数/节流/断线重连），`mock Foxglove bridge: PASS`
- 固件仓：`node --check`（产物与 `main.js`）、`git diff --check` PASS
- 导航仓：`npm run build` ✓、`npm run build:package` exit 0、`npx vitest run` → 3 failed/45 passed 文件、7 failed/153 passed 用例；7 个失败全部位于 `src/utils/__tests__/normalizeMaps.test.ts`、`src/features/dashboard/__tests__/DashboardPage.test.tsx`、`src/features/dashboard/__tests__/ModePanel.test.tsx`，均为本次 diff 未触及模块的**既有失败**

## 5. 关键技术事实（后续别重摸）

- ROS1 foxglove_bridge：通道编码 **`ros1`（原生 ROS1 二进制线序）**、schema 为 ROS1 `.msg` 全文、**服务调用仍是 JSON**、客户端发布只接受 `ros1`；**ROS1 侧不存在「foxglove + CBOR」** —— CBOR 只活在本次删除的 rosbridge 补丁里。noetic 有二进制包 0.8.4-1（上游 README 建议 ROS1 从源码构建，当前 0.8.5）。
- 视频早已不在 WS 上：固件 1.0.21~1.0.23 把 HTTP MJPEG 内置进相机节点（默认 `~preview_enable=true`、`~preview_port=5010`、`~preview_path=/api/camera/preview.mjpeg`、fps 10 / scale 4 / Q70 / 顺序 `CAM_B,CAM_A,CAM_C`，无客户端时不合成）；APP `RobotEndpoint.kt:36` 已在用。**用户明确禁止本次使用 5010**，故 5001 控制台仍订阅 `/keyframe`（现在是二进制）。
- 产品分层：基础款＝固件仓（core/firmware-sensors/ota_web；3D 重建由 base 自己 `roslaunch faster_lio mapping_avia.launch`）；2D 导航＝外挂容器（5000/80/19090）。**固件仓对导航引用 0 处**，依赖方向只有 nav → base，桥只落 base。

## 6. 未完成 / 风险 / 下一步

1. ⏳ **未部署、未真机验证**：等用户上班在 701 编译（`compile.bash` + `docker build`）与 compose 部署；`ros-noetic-foxglove-bridge` 在 runtime-base 基础镜像上的可装性**未实测**（若 noetic apt 源不可用，需改为源码构建 0.8.5）。
2. ⏳ APP 未改（后续单独一轮）；导航 SPA 已改但未真机联调。
3. ⏳ 切到 Foxglove 后，旧 APP / 旧 SPA 在 D360 上连不上属**预期**，不计为验收失败。
4. ⚠️ 风险：`src/device_service/launch/project_control.launch` 仍 include rosbridge，而 `.codex/AGENTS.md`/`.claude/CLAUDE.md` 仍称它是「生产环境入口」；若确有部署按它启动，rosbridge 会占 9090 且与页面协议不兼容 → 上机测试时一并确认去留。
5. ⏳ 未决：两条 MJPEG（base `:5010` vs 导航 `:5000/api/camera/stream.mjpeg`）是否以 5010 为唯一来源；shim 单一来源的最终形态（vendored 单文件 vs 独立仓 + npm 依赖）。
6. ⏳ 未决：导航仓三条分叉线（`f281b8e` / `698be43` / `1ad7809`→`4e13055`）是否收拢。

## 7. 禁止 / 回滚

- 未合并任何分支、未 force push、未改历史、未动设备与其它 worktree。
- 回滚：固件仓 compose 换回旧 tag（`…firmware:1.0.23` 与 `rollback-1.0.16-20260917` 均在 ACR）；代码侧 revert 任务分支提交即可（无运行时开关需要还原）。
## 8. 第二轮追加（2026-09-19 深夜，用户追问后）

- 固件仓 `d29014b`（已推送 `codex/d360-foxglove-link-20260919`）：
  - **删除** `src/device_service/launch/project_control.launch`（历史一体化 launch：服务＋livox＋OAK＋rosbridge 一把起）。产品真实入口是 compose：`core`（core.launch）＋ `firmware-sensors`（sensors.launch）＋ `ota_web`（setting_server）。
  - 文档同步：`.codex/AGENTS.md`、`.claude/CLAUDE.md`（启动命令改 compose；启动流程改成三容器；补「已删除，别再用」提示）、`docs/debug_guide.md`（原 `roslaunch --verify project_control project_control.launch` 换成对 `core.launch` / `sensors.launch` 的 XML 解析校验）。
  - 复核：全仓除上述说明文字与 `.git` 内部外，已无 `project_control.launch` 引用。
- 导航仓 `29b7482`（已推送 `kunkunwei/codex/foxglove-link-20260919`）：
  - 删掉 rosbridge 专有死参数 `compression` / `queueLength`（`rosClient.ts`、`Viewer3D.tsx`、`PointCloudLayer.tsx`、`usePointCloud.ts`）并同步 2 个测试断言；只保留仍生效的 `throttleRate`（点云 4Hz）。
  - 验证：`npm run build` exit 0、`npm run build:package` exit 0、`vitest` 回到基线失败集合（3 文件 / 7 用例）。
- 陈旧测试取证（回答「为什么单测本来就是红的」）：3 个失败测试文件最后改动均为 `6dfbbbc`（2026-08-09「实现音频播放」），其被测实现分别推进到 `e2e71bc`(08-19)、`bff106c`(08-25)、`f382a5b`(09-04)；在基线 `4e13055` 上单独跑同样 3 个文件，失败集合与报错逐条一致 → 属测试未跟随实现的漂移，不是运行缺陷（与「实机正常」不矛盾）。
- 仍未决：视频链路方向（现状为 HTTP MJPEG：二进制、无 JSON/base64，但逐帧全 JPEG）与两条 MJPEG（base `:5010` / 导航 `:5000/api/camera/stream.mjpeg`）的收口，等用户选定后单开一轮。## 9. 链路规划核查记录（2026-09-19，为「HTTP/JSON 与视频链路规划」取证；本轮未改代码）

### 9.1 两条 MJPEG 并非同内容（纠正前文说法）
- base（固件相机节点，`:5010/api/camera/preview.mjpeg`）：订阅三路相机 → **三路拼接 B,A,C**（`~preview_cam_order`），scale 4、Q70、10fps；一次合成 + 每客户端一线程只发最新帧，`PREVIEW_MAX_CLIENTS = 8`（超限拒绝）→ **CPU 不随客户端数增长，带宽 N 倍**。
- 导航（`d360_nav2D/src/nav_api/fastapi_service/capture.py:419`，`:5000/api/camera/stream.mjpeg`）：订阅**单相机** `CAMERA_TOPIC`（默认 `/SLB_CAM_A/compressed`），`?profile=video_link` 时按目标比例（默认源帧 50%）重编码；`_STREAM_CACHE` 以 `(received_at, width:quality)` 为键缓存 → **重编码每源帧只做一次，跨客户端共享，CPU 也不随 N 增长**。
- 结论：两条是「同一目的、两套实现、内容不同（拼接 vs 单相机）」，仍应收敛为一条，但不是简单删掉其一。

### 9.2 多客户端并发现状（代码证据）
- **遥控**：APP 直连 `:9090` 发 `/cmd_vel_web`（约 10–25Hz），nav_api 的 `teleop.py` 转发到 `/cmd_vel`；转发由**全局开关** `/api/teleop_key/enable` 控制，内部只缓存「最近一次有效 Twist」→ **多台 APP 同时驱动 = 谁最后发谁赢；任何一台都能全局 disarm 触发急停**。
- **模式互斥**：`control_ownership.py` 是**进程内**闩锁（`AUTO/MANUAL_PENDING/MANUAL/MAPPING_PENDING/MAPPING`），只对 HTTP 触发的模式切换 fail-closed；其文件头明确写「does not replace ROS process state」，**管不到 ROS 层的 /cmd_vel_web**。
- **客户端计数**：全仓无人引用 `/client_count`、`/connected_clients`（那是 rosbridge 插件发布的，随 rosbridge 一起消失）；Foxglove 桥不提供等价主题 → 若产品要显示「谁在看/谁在控」，需自己发一个 owner/客户端状态主题。
- **带宽量级**：`/global_cloud_navigation` 0.56–0.75MB/帧 @4–5Hz ≈ **18–25Mbps/客户端**；视频现状 ≈ 2.8Mbps/客户端（base 5010）或按 `video_link` 目标比例；`/keyframe` ≈ 0.39MB×4.3Hz ≈ **13Mbps**（WS 上，已改二进制但仍是大图）。
- **Foxglove 桥多客户端**：每客户端独立连接与发送缓冲（`send_buffer_limit` 默认 10MB，超限丢旧消息）→ 慢客户端不拖累他人。

### 9.3 两个解码库都是二进制
- `@foxglove/rosmsg-serialization` = **ROS1 线序**（按 `.msg` 顺序、小端、字符串/数组带 4 字节长度）；`@foxglove/rosmsg2-serialization` = **CDR**（OMG CDR，4 字节封装头 + 对齐填充）。二者都吃 `@foxglove/rosmsg` 解析出的定义（ROS1 用 `ros2:false`），差别是线序而非 JSON/二进制。
- ROS1 桥只通告 `ros1` 一种编码；ROS2 桥通告 `cdr`（JSON 仅用于客户端发布侧）。topic 载荷在两个产品上都是二进制；JSON 只剩：服务调用（协议规定）+ 发布者塞进 `std_msgs/String` 的 `/topic_frequencies`、`/system_monitor_history`。## 10. 第三轮：删除 `/keyframe` + `oak_keyframe_stitcher`，控制台视频改用通用 MJPEG 端点（2026-09-19）

- commit **`11d0e98`**（固件仓 `codex/d360-foxglove-link-20260919`，已推送）：12 文件、+24/-159。
- 删除清单：`sensors.launch:44-50`、`oak-camera_driver/launch/oak_hardware_trigger_ros.launch:13-19`、`scripts/oak_keyframe_stitcher.py`（整文件）、`CMakeLists.txt`（CYTHON_EXECS + DEPENDS 各 1 行）、`setup.py`（scripts 项）、`SystemMonitor.py`（keyframe_hz_monitor + `/topic_frequencies` 键）、控制台 `templates/index.html` / `static/main.js`、`docs/debug_guide.md:144`、`.codex/AGENTS.md:95`、`.claude/CLAUDE.md:99`。
- 控制台实时画面：改用相机节点**既有**端点 `http://<host>:5010/api/camera/preview.mjpeg`，元素改为 `<img id="liveImage" style="width:100%;height:auto;display:block">`；WS 连接时设 src、error/close 时清空 src（相机节点随即回到空闲、停止合成）。`/topic_frequencies` 里的 keyframe 项换成 `/SLB_CAM_A/compressed`（`SystemMonitor` 新增 `camera_hz_monitor`），控制台 Hz 标签 `Keyframe:` → `Camera:`。
- **裁剪根因（用户关心）**：旧控制台把 1440×300 的三路拼接图用 `ctx.drawImage(img,0,0)` 硬画进 `640×512` 的 canvas → 左右被裁掉。编码链路本身（scale 4 + hstack；导航侧等比 resize）一直**只缩放不裁剪**。现在 `<img width:100% height:auto>` 完整显示、保持宽高比。
- **3D 重建不受影响**（证据）：SLAM 用 `faster_lio`（只吃 `/livox/lidar`+IMU）；重建着色 `lidar_add_rgb` 的 `config/mono.yaml:38` 直接订阅 `/SLB_CAM_A/compressed`；项目预览 `/project_image` 是 `device_basic_service.py:144` 读落盘图片；相机节点注释自己写明「`/keyframe` 只是显示用派生图」。
- **APP 侧影响（本轮未改，APP 轮处理）**：`NativeDataCollectionSession.kt:175-177` 有一条 `/keyframe`（`sensor_msgs/CompressedImage`）fallback，「仅在 HTTP 预览不可用时订阅」→ 现在该 fallback 永久失效（预览流异常时 APP 再无兜底画面），APP 轮应把这套 `subscribeKeyframeFallback/removeKeyframeFallback` 机制一并删掉；`/topic_frequencies` 键名变化后，APP 若仍按 `/keyframe` 取值会得到 `undefined`（显示 `-- Hz`，不报错）。
- 用户决定（本轮同时确认）：①「同一时刻只有一个 APP」的互斥功能**暂不做**（客户不会多 APP 同时连同一台设备）；②浏览器能抢控制权的**根因是 WEB 导航页没做手动/自动切换**（待补 WEB，不动 nav_api 语义）；③视频展示**不允许裁剪**（已落实在控制台）。
- 待定：视频路线（先把三条并成一条 MJPEG 再换 x264＋fMP4 vs 直接 x264）、WEB 手动/自动切换是否立即补、导航侧 `:5000/api/camera/stream.mjpeg` 的收口时机。## 11. 视频第二轮：**B1 已实施完成**（x264 软编 + MPEG-TS over HTTP，2026-09-19）

> 固件仓 commit **`cdb189a`**（已推 `codex/d360-foxglove-link-20260919`）：相机节点 +293/-75、控制台 main.js +32/-8、vendored `mpegts.min.js`(1.8.2, 275767 B, sha256 `270dd3b1…6337`)、index.html、Dockerfile、两份架构文档。
> 端点：`http://<host>:5010/api/camera/preview.ts`（`Content-Type: video/mp2t`），状态 `…/preview.ts/status`（clients/fps/kbps/bytes/ffmpeg_alive/codec）。
> 关键设计：**一个常驻 ffmpeg 只编一次**，多客户端共享同一条 TS 流扇出；每客户端 1MB 有界队列（满则丢最旧块）；无客户端不喂帧且进程不存在（空闲零 CPU）；0→1 客户端时重建进程（≤1s 出关键帧，`-g = fps`）；ffmpeg 意外退出先记 stderr 尾、重启一次，再退则本会话放弃（等下个客户端）。`~preview_quality` 作为死参数删除。
> ffmpeg 参数：`-f rawvideo -pix_fmt bgr24 -s WxH -r fps -i - -an -c:v libx264 -preset ultrafast -tune zerolatency -g fps -pix_fmt yuv420p -b:v 800k -maxrate 1M -bufsize 500k -loglevel error -f mpegts -`（与 715 上已验证的 RTSP 推流同套编码参数；有意去掉 `-re`，未加 `-threads 4`）。
> **Dockerfile 显式加装 `ffmpeg`** → "容器里有没有 ffmpeg"不再是未知数（但**必须重建镜像**才生效）。

### 11.1 主代理独立复核（非转述）
- `py_compile` OK；`node --check main.js` OK、`node --check mpegts.min.js` OK；`diff --check` 无输出。
- 源码零残留（`preview.mjpeg`/`multipart`/`_mjpeg_part`/`preview_quality`/`liveImage`/`LIVE_IMAGE_URL` 均为 0；早先出现的 3 个"命中"只在 `.git/COMMIT_EDITMSG` 的提交信息文本里）。
- 复核了代码：`PreviewTsEncoder.cmd/start/alive/stop`、`PreviewTsClient.offer/_stream`（有界队列、`video/mp2t` 头、`Connection: close`、注册后才发头避免漏开头画面）、`_accept_loop` 仍限 8 客户端、`status()` 字段齐全、`_ensure_encoder` 的重启逻辑只有一条路径。风格与仓内既有代码一致，未见多余状态机。

### 11.2 未验证（必须上机，按顺序）
1. **重建镜像**（新 Dockerfile 层会装 ffmpeg）→ `docker exec firmware-sensors ffmpeg -encoders | grep 264` 确认 libx264。
2. 起节点看日志与 `curl -s http://127.0.0.1:5010/api/camera/preview.ts/status`（`ffmpeg_alive=true`）。
3. `curl -N -o /tmp/x.ts …/preview.ts` 拉 5s → `ffprobe` 应报 `h264 / 1440x300 / 10 fps`；记录 `kbps`（预期 ≈800）与 ffmpeg 线程 CPU。
4. 断开后 `pgrep ffmpeg` 应无残留、CPU 掉回 0。
5. 浏览器开 5001 控制台：**≤1s 出画、完整三格不裁剪**；再开第二个标签页验证 `clients=2` 与扇出。
6. `rostopic hz /SLB_CAM_A/compressed` 确认导航侧拍照链路未受影响。
7. 未验证风险点：Jetson 上 x264 实际 CPU（估计 0.3–0.5 核，若抢 FAST-LIO 就加 `-threads 4`）；慢客户端丢块后的花屏恢复；Safari/iOS 的 MSE 兼容性（Chrome/Edge 预期正常）；奇数尺寸会让 yuv420p 报错（当前默认尺寸为偶数，已够用）。

### 11.1 现状（已核实）
- 唯一视频端点＝相机节点内嵌 HTTP MJPEG：`http://<host>:5010/api/camera/preview.mjpeg`（三路拼接 B,A,C、`~preview_scale=4`、`~preview_quality=70`、10fps；无客户端不合成；`/api/camera/preview.status` 报 clients/fps）。
- 控制台（5001 页面）与 APP 都走这一条；`/keyframe` 与 `oak_keyframe_stitcher` 已删除；导航侧 `:5000/api/camera/stream.mjpeg`（单相机 + `?profile=video_link` 重编码）待删（APP 改用 5010 之后）。
- 带宽/CPU 量级：MJPEG 现状 ≈ 35KB/帧 × 10fps ≈ **2.8Mbps**，合成 ≈ 0.25 核；x264（ultrafast+zerolatency，1440x300@10fps）≈ **0.8Mbps**、约 0.3–0.5 核。
- **D360S 侧没有等价端点**：其控制台是订阅 `/SLB_CAM_A|B|C/compressed`（每路 10Hz CompressedImage）走 WS 显示 → 大图仍在 WS 上（即 D360 刚消掉的队头阻塞形态）。D360S 未发布，可直接按工程规范改。

### 11.2 两条候选路线
- **A. 保留 MJPEG、只调参数**（`~preview_scale` 4→6/8、`~preview_quality` 70→60）：零客户端改动，带宽可降到约 1–1.5Mbps；仍是逐帧全 JPEG，画质最差。
- **B. 换 H.264（用户倾向）**：合成后一次软编 x264 → 单一 H.264 流，带宽约 0.8Mbps、画质更好。需要决定**容器与播放端**：
  - B1：H.264 → **MPEG-TS over HTTP**（`Content-Type: video/mp2t`）。浏览器用 `mpegts.js`（需 vendor 一个约 100KB 的库 + MSE）；Android `ExoPlayer` 原生支持 TS；VLC/ffplay 直接可播。
  - B2：H.264 → **fMP4 over HTTP + MSE**：浏览器需自己写/引 muxer，工程量大于 B1。
  - B3：裸 H.264 + WebSocket + WebCodecs：只 Chrome 好，不采用。
- 编码实现位置：相机节点合成线程之后。**必须先确认容器内有无 ffmpeg/libx264**（现有 `oak_rtsp_pusher.py` 是宿主 tmux 里跑 ffmpeg，容器内是否有未验证）。

### 11.3 上机（701/715）核对清单 —— 跑完再决定 A/B
```bash
# 1) 容器内有没有 ffmpeg / libx264（决定 B 是否可行）
docker exec firmware-sensors bash -lc 'which ffmpeg; ffmpeg -hide_banner -encoders 2>/dev/null | grep -i 264'
docker exec firmware-sensors bash -lc 'python3 -c "import cv2;print(cv2.__version__)"'

# 2) 现有预览的真实码率与 CPU 基线（先量再改）
curl -s http://127.0.0.1:5010/api/camera/preview.status
# 另开一端拉流 30s，统计字节数：
timeout 30 curl -s http://127.0.0.1:5010/api/camera/preview.mjpeg | wc -c
docker stats --no-stream firmware-sensors

# 3) 单路 x264 软编的 CPU 实测（不接 UI，只测编码器本身）
#    用同样尺寸的合成帧喂 ffmpeg 10fps，观察 top 里的 ffmpeg CPU

# 4) 浏览器端：Chrome 打开 5010 的 <img>（现方案）与候选 mpegts 播放页各 5 分钟，记录
#    首帧时间、卡顿次数、是否有画面裁切（必须完整三路、等比缩放）
```

### 11.4 与其它决定的联动
- 视频**不允许裁剪**（只等比缩放）；网页与 APP 的容器宽高比要跟随流本身。
- 若选 B，则同轮改：相机节点（编码+容器+端点）、5001 控制台（`<img>` → `<video>`+MSE）、导航 SPA（若显示视频）、**APP（ExoPlayer）**——即"一次换编码"而不是两条并存。
- 若选 A，则本轮只做参数调整 + 删导航侧 `:5000`；x264 另立一轮。
- 无论哪条：**D360S 要对齐一个同样的 5010 端点**，否则 APP 得为 D360S 保留第二条视频路径（回到冗余）。## 12. 第四轮：WEB 手动/自动切换 + 删除导航侧视频端点（2026-09-19，均已推云）

固件仓无改动；导航仓 `kunkunwei/codex/foxglove-link-20260919` 三个新提交：

| 提交 | 内容 |
|---|---|
| `a5f9c45` | **② WEB 手动/自动切换**：`ModePanel` 新增「手动接管」（`POST /api/control/mode/manual/force`）与「回到自动」（先 `enableWebTeleop(false)` 再 `GET /api/control/mode/navigation`）+ 每 2s 轮询的手动/自动标签；删掉失效且有害的浏览器键盘遥控（`TeleopPad`/`useTeleop`/`sendTeleopKey`） |
| `1a5aaed` | **③ 删导航侧 `:5000/api/camera/stream.mjpeg`** 单相机 MJPEG + `?profile=video_link` 重编码（`capture.py` −177 行、`app.py` −2）+ 删除随之失效的 `Dockerfile.video-link-overlay` |
| `da775f1` | 删掉随视频端点一起失去调用的 `_bounded_env_float` |

### 关键事实（本轮核实）
- **`GET /api/teleop_key/send` 在本仓现状与历史都不存在**（`git log -S "teleop_key/send"` 为空）→ WEB 的键盘遥控一直在打 404；后端只暴露 `/api/teleop_key/enable` 与 `/status`。
- 手动接管的后端流程很完整：`POST /api/control/mode/manual/force` 一次完成「claim MANUAL_PENDING → 取消自动导航 → 发零速 → `teleop_force_enable` → claim MANUAL」，返回 `ownership/teleopEnabled/navigationCancelled/warnings`。
- 「回到自动」顺序经核实正确：`enable=false` → `teleop.disable(claim_auto=True)` 发零速+恢复被暂停任务+claim AUTO；随后 `GET /api/control/mode/navigation` 成功再 claim 一次 AUTO。
- 拍照链路完好：`take_photo` / `/photo` / `/list` / `get_latest_frame_snapshot` / `CAMERA_FRAME_MAX_AGE_S`（内联读环境变量）全部保留，`CAMERA_TOPIC`（默认 `/SLB_CAM_A/compressed`）订阅未动。
- 删除后全仓零残留：`stream.mjpeg`、`_mjpeg`、`video_link`、`camera_router`、`CAMERA_STREAM_FPS`、`CAMERA_VIDEO_LINK_*` 均无命中；`Dockerfile.video-link-overlay` 无任何脚本/CI 引用。

### 验证（主代理亲自复核）
- `python -m py_compile capture.py app.py` OK；`npm run build` exit 0；`npx vitest run` = **3 文件 / 7 用例失败，与基线 `4e13055` 同一批、无新增**（`normalizeMaps` 2、`DashboardPage` 4、`ModePanel` 1，均为陈旧断言）。
- 全仓 grep 无残留；`git -c core.whitespace=cr-at-eol diff --check` 无输出；`master`(4e13055) 未动。

### APP 侧连带影响（预期，已在交接文档登记）
- `RobotEndpoint.cameraStreamUrl`(5000) 与 `videoLinkCameraStreamUrl` 从此 **404**；APP 改造后只用 5010。
- 交接文档：`.ai-workspace/handoff/APP-FOXGLOVE-LINK-HANDOFF-2026-09-19.md`（含 §9 跨产品缺口：D360S 侧没有 5010 等价端点，其控制台仍从 WS 拉三路 CompressedImage）。

### 剩余
1. **① 视频换编码**：设计就绪见 §11，**卡在路线决策（A 调参 MJPEG / B x264 + MPEG-TS）+ 上机核对容器内有无 ffmpeg/libx264**。
2. **④ 真机编译/部署/验收**：等设备与用户在岗。
3. **D360S 侧 5010 等价端点**：服务端任务，决定 APP 是否要保留两条视频路径。## 13. D360S 侧补齐同一视频端点（2026-09-19，已推 gitee）

> 目的：让 APP 只保留**一条**视频路径（两产品都是 `:5010/api/camera/preview.ts`），不造兼容层。
> D360S 仓 `electech6/SLAMIBOT_D360_Framework`，分支 `codex/d360s-foxglove-cbor`，commit **`f732eb4`**（起点 `8e83f1c`）：7 文件 +837/-91。

| 文件 | 内容 |
|---|---|
| `src/oak_cam_ros2/scripts/oak_hardware_trigger_ros2.py` | +771：内嵌 HTTP MPEG-TS 预览（ffmpeg/x264）。**逐字照搬 D360 设计**（`PreviewTsEncoder`/`PreviewTsClient`/server/`status()`/`_ensure_encoder`），只做 rospy→rclpy 适配（`declare_parameter`/`get_parameter`、`node.get_logger()`、`finally` 里 `stop()`）。参数与 D360 同名同默认值（`preview_port=5010`、`preview_path=/api/camera/preview.ts`、`fps=10`、`scale=4`、`cam_order=CAM_B,CAM_A,CAM_C`）。**三路 `/SLB_CAM_*/compressed` 发布逻辑未动**（`lidar_add_rgb` 着色 + `SystemMonitor` Hz 仍依赖） |
| `install.bash` | `APT_PACKAGES` 加 `ffmpeg`（该数组同时是安装后校验清单） |
| `runtime.bash` | `matching_processes()` awk 白名单加 `ffmpeg`（审计能看到子进程） |
| `ota_server/web_page/static/modules/mpegts.min.js` | 新增——与 D360 **同一个 git blob**（`887013547cc03df9f3668d2018364efd1ec5cee9`，版本 1.8.2） |
| `templates/index.html` | 三格相机面板 → 一个 `<video id="liveVideo" muted playsinline style="width:100%;height:auto;display:block">`（不裁剪）；引入 `mpegts.min.js`；Hz 行保留 |
| `static/main.js` | 删 `setupCameraSubscribers`/`cameraSubscribers`/`cameraFrameSequences`/`jpegObjectUrl` 与相关 CSS；加 `TS_URL` + `startLiveVideo/stopLiveVideo`（与 D360 同形状） |
| `README.md` | 端口/链路描述同步 |

### 主代理独立复核（非转述）
- `py_compile` OK；`bash -n install.bash runtime.bash` OK；`node --check main.js` 与 `mpegts.min.js` OK。
- `mpegts.min.js` 两仓 `ls-files -s` 同为 `88701354…`（同一 blob）。
- 零残留：`setupCameraSubscribers`/`cameraSubscribers`/`cameraFrameSequences`/`cameraAImage`/`jpegObjectUrl` 均 0；三路发布逻辑的 diff 里只有一条新增注释。
- 抽查接线：`push_frame` 在主循环收帧处调用（`1200`）、`_start_preview_server` 在启动处（`1163`）、退出时 `preview_server.stop()`（`1263`）、ffmpeg `cmd()` 与 D360 逐字一致。
- 未真机验证（本机无 ROS2/ffmpeg/DepthAI/OpenCV）；子代理另做了一份 stub 注入的 40 项断言（已删除 harness），属桩验证。

### 上机第一步（D360S，`jetson@192.168.31.35`）
```bash
ffmpeg -version                                    # install.bash deps 之后应存在
ss -ltnp | grep -E ':5010|:9090|:5001'             # 5010 应归 oak_hardware_trigger_ros2
curl -s http://127.0.0.1:5010/api/camera/preview.ts/status
curl -s -D - -o /dev/null --max-time 3 http://127.0.0.1:5010/api/camera/preview.ts | head -8
ps -eo pid,args | grep -E 'ffmpeg|oak_hardware'    # 无客户端时不应有 ffmpeg
ros2 topic hz /SLB_CAM_A/compressed                # 三路发布不受影响
```
然后开 `http://<IP>:5001` 看 `<video>` 出画、三格顺序是否与物理装法一致（不裁剪）。

### 未验证/风险
1. D360S 上 5010 是否与其它进程冲突（离线不可判；冲突时预览停用、相机照常出图）。
2. `preview_cam_order` 默认 `CAM_B,CAM_A,CAM_C` 是否与 D360S 物理装法一致（真机看画面；临时改：`--ros-args -p preview_cam_order:=CAM_A,CAM_B,CAM_C`）。
3. x264 在 D360S 上的 CPU 与三路 JPEG 发布叠加后的占用（预览只在有客户端时跑）。