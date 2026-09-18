# Context Checkpoint — 2026-09-17 深夜：视频链路改回 MJPEG 50%（代码层已推完，只剩出镜像 + 上机验收）

> 主线交接：`.ai-workspace/handoff/MJPEG-VIDEO-LINK-TUNE-50PCT-HANDOFF-2026-09-17.md`（§0.1 进度快照、默认值取舍原则、交付模型、§5 验收清单）
> 设备/踩坑：`handoff/SESSION-HANDOFF-2026-09-17.md`；运维铁律见 `procedures/`、`known-issues/`（不往检查点堆）
> ⚠️ 本文件 2026-09-17 深夜被**两个 AI 并发写过**（一度互相覆盖）。改动前先重读全文，别只追加。

## 语音容器化（2026-09-18）：✅ 715 已上线并验收通过
- **单一事实源 → `tasks/voice-containerization-plan-2026-09-18.md`**（方案/隐式契约/P0 实测/交付物/验收/红线/踩坑全在里面，此处不重复）。
- ✅ **有效镜像 `d360_voice_assistant:1.0.2`**（digest `sha256:26cfc05c…`，arm64/595MB）；⛔ **1.0.0 与 1.0.1 作废**：1.0.0 把厂商 demo appid 真值打进镜像；**1.0.1 漏写 `ENTRYPOINT`** → 容器跑基础镜像默认 `/bin/bash`、无 TTY 读到 EOF 立刻 exit 0（表现为"启动成功却秒退"、5011 永不起、装机脚本 health 超时回滚）。已加构建期断言 `Entrypoint 非空`。
- ✅ **ACR 已设为公开**（用户操作）：715 无凭据下 `docker manifest inspect …:1.0.2` **匿名可访问 ✓**，出货路径验证通过；一键脚本走的就是普通 `docker pull`，与 `install_2d_nav.sh` 一致。
- ✅ **715 已部署验收**：`voice-assistant` 容器 Up、5011 health 200、容器内可见 ListenGo + USB 音箱、**`run_mic` 到 `WAIT_WAKE`**、旧 crontab 已摘、`slamibot-audio-node-sync.service` 在跑、nav 容器仍能见音箱（播报不受影响）。**装后自验 8/8 PASS**。
- ✅ **旧源码已移出**（非删除，可人工确认后再清）：`/home/jetson/voice-old-source-20260918-120724`；**凭据 `/home/jetson/xf_chat_standalone/xf_config.yaml` 保留（0600）**，容器只读挂载它。
- ✅ **凭据搬运**：701→715 三个值哈希逐一相同；讯飞在线 TTS + 星火对话实测通过；**到点播报 `job=COMPLETED / played=True`**。
- ✅ **一键脚本原地改造完成**：`voice/install_voice_assistant.sh`（含旧版自动迁移）。踩坑已修：`crontab` 必须 `-u "$TARGET_USER"`（sudo 下默认读 root 的）；`[ -n "$pids" ] && {…}` 在 `set -e` 下会**静默杀死脚本**（改 `if`）；回滚必须**先按名删容器再还原 compose**。
- ⚠️ **待修（小）**：脚本自验里 `chk "旧 crontab 自启已摘除" "! crontab -l …"` 少了 `-u` → 会**假 PASS**。
- ⚠️ **遗留**：① 715 的 USB 线曾脱落（已插回，见 `known-issues/box-usb-branch-drop-and-can0-reattach-2026-09-17.md` §6）；② 我一度把 `EBUSY` 误判为 PA 占卡，实为**我自己的 `pactl` 观测者效应**，结论已改正、**不要动 PA**；③ 4G：SIM 已由用户拔下，待写客户绑定文档；④ vosk 容器化、语音容器是否自带 tts_cache 兜底 —— 均待做。
- **注意**：`docker compose up -d voice-assistant` 会顺带把与 compose 不一致的容器收敛（本次 `core` 被从 1.0.22 重建到 1.0.23，nav 未受影响）。

## 刚完成（代码层已全部推完）
- **导航** `kunkunwei/Scout_mini_navigation` 分支 **`codex/mjpeg-video-link-50pct-20260917` @ `b6bec0d`**（**未合并 master**），2 文件：
  - `capture.py`（`b4a6dfe`，+41/−14）：新旋钮 `CAMERA_VIDEO_LINK_TARGET_RATIO`（默认 0.5 / clamp 0.2–1.0）取代写死的 `0.18`；`MAX_WIDTH` 480→1280（clamp 640–1920）；`JPEG_QUALITY` 40→80（clamp 60–90）；`FPS` 20→10；降级阶梯加地板（宽度 ≥ `max(960, 0.75*max_width)`、质量 ≥60）**触底即停**（旧代码会掉到 160px/Q20）。
  - `ros_client.py:461`（`b6bec0d`，1 行）：`CAMERA_TOPIC` 默认 `CAM_B`→**`CAM_A`**（已裁决保留，见下）。
- **固件** `kunkunwei/SLAMIBOT_D360` main **`e799f1b`**：**做法 B 已执行**（revert 5 个提交，4 文件 +3/−994）。独立自证：`git diff 28a2cc7 origin/main -- src/oak-camera_driver` **为空**、OAK 包内再无 `ws_port`/`h264`（5010 消失）、整体只差 `device_basic_service.py` 版本号 3 行。
- 源码级核实（取代交接文档 §8「需上机核对」1/2/6）：部署 1.2.3 的 `capture.py` blob == `kunkunwei/master`(1ad7809) == 改前本地 `bb2fe15`；master **无** video_link 测试文件（`5ad6000` 加过、未进 master）→ 无需改测试。
- 「开始作业数据采集」澄清：**与 5010 无关**，走 rosbridge `:9090` + `/keyframe` + `rosbridge_patch/`（`60560bb`，revert 未触碰），属重建红线，**不改**。

## 有效事实源
- 相机按机型：**715 = `CAM_A` 前/中间**；**701 老机型 = `CAM_B`**。
- ✅ **`CAMERA_TOPIC` 已裁决（用户，2026-09-17 深夜）：保留 `b6bec0d`，代码默认 `CAM_A`**。原则：**新设备一键部署、交付客户后不能随意改 → 默认值必须按新机型（715）取；701 是开发机，随时可手工改**（需要时 `CAMERA_TOPIC=/SLB_CAM_B/compressed` 覆盖）。
  - 「不改默认值、改在 715 compose 加 environment」**作废**：新机开箱即看到侧面相机；且 `install_2d_nav.sh` 升级路径只改 `image:` 行、不会自动补 environment。
  - 副作用（用户已接受）：该帧缓存同时供实时视频与**拍照取帧**，拍照来源也一并变成前相机。
  - ⚠️ **推广：所有按机型的默认值一律取新机型。** 已核对 `oak_keyframe_stitcher` 的 `cam_topics` 顺序 `B,A,C` = 左,前,右，对新机型已正确，**不要"顺手改"**（重建红线）。
- 交付模型：**设备上的东西都靠脚本从阿里云 ACR 拉镜像**（`registry.cn-shanghai.aliyuncs.com/slamibot/...`）。**推 Git 只是开发动作，交付物是 ACR 镜像**；**Gitee 不在部署链路上**（用户已定：暂不动 Gitee；固件 Gitee 停在 1.0.15 已不算隐患，此前那条"待决策"关闭）。
- 源流被 STM32 硬触发锁死 **10.000 fps**；OAK 同时最多 **5 个编码器**（3 路 MJPEG 供 `/keyframe`，余 2）。
- 量测：`tmp/mjpeg_measure.py`（真机）；`tmp/mjpeg-verify/verify_video_link_ladder.py` + `pylibs/`（本地离线复算，打桩依赖加载真实 capture.py）。

## 715 部署与验收（2026-09-18 上午，已完成大部分）
- **已上线**：固件三容器 → **1.0.21**（`sha256:dc6682da…`）；`scout-nav` → **`d360_nav2d:1.2.4`**（`sha256:d525b7f5…`）。重建顺序正确（core 先起 → **scout-nav 最后**）。
- 验收 PASS：**5010 监听已消失** ✓；三路相机 **10.000 / 10.006 / 9.626 fps** ✓；`/keyframe` 4.0 Hz ✓；5001=200 ✓；串口 ttySTM32/ttyRTK 正常占用 ✓；nav `/health` rosbridgeConnected=true ✓；**容器内无任何 `CAMERA_*` 环境变量** ✓（代码默认生效，证明"改代码默认"比"compose 加 environment"更对）。
- **踩坑**：715 刚开机时时钟是 1970 → `docker pull` 因 TLS 证书校验失败被拒（"current time 1970 is before 2026-03-23"），等 NTP 同步（约 1 分钟）后正常。**compose 已先改成新 tag、容器仍是旧镜像** 的那几十秒是有风险的（此时重启会因本地无镜像而失败）→ 以后要么先拉镜像再改 compose，要么改完立刻重建。
- **底盘无法激活 —— 非软件问题（用户已确认底盘/BOX 都没接）**：`can0` 起初**根本不存在**；`modprobe mttcan` 后出现并 UP，但 `cansend` 后 TX 仍为 0 且 `berr-counter tx 248 → BUS-OFF` —— 这是"总线上没有对端"的典型特征（无 ACK）。已复位回 ERROR-ACTIVE。
- ⚠️ **顺带挖到一个真实产品缺陷（用户已明确"不用浪费时间搞这个"，故只记录、未改代码）**：**`/etc/modprobe.d/denylist-mttcan.conf` 是 NVIDIA L4T 自带文件**（`2026-01-27`、NVIDIA 版权头），内容 `blacklist mttcan`。黑名单只挡"按别名自动加载"，显式 `modprobe mttcan` 有效 —— 而**设备上没有任何机制会显式加载它**（`d360_deploy` 全文无 mttcan/modprobe；无 systemd 单元）。导航侧 `_reconnect_can_locked()` **只做 `ip link set can0 up type can bitrate 500000`，代码里没有 modprobe**（`base_mode.py:824-842`）→ 因此**每次冷启动 `can0` 都不存在，底盘激活永远是 NONE**，与选 auto/scout 无关。**待有底盘时验证**，修法建议：把 `mttcan` 写进 `/etc/modules-load.d/`（显式加载），并纳入 `d360_deploy` 一键装机。

## 50% 压缩的真机验收数据（2026-09-18）
- **带宽达标**：默认档（原图直通）**18.86 Mbps / 7.85 fps / 单帧 293.3 KB**；`?profile=video_link` **5.84 Mbps / 6.76 fps / 单帧 105.4 KB** → 单帧压到 **36%**（算法是"≤目标即停"，比 50% 更狠），带宽降到 **31%**。
- ✅ **帧率问题已定位并修复**（`c5b8933`，镜像 **1.2.5** `sha256:c01fd0a0…` 已部署 715）：
  - **真因不是重编码，也不是 ingest** —— 用 roslibpy 在容器内实测 ingest 路径：**10.00 fps / 23.79 Mbps（满帧，无上限）**；单帧重编码也只是 32–56 ms。
  - **真因是 `_mjpeg_frames()` 的帧节奏**：每周期的 `time.sleep(interval)` **没扣掉本周期已耗时**，于是编码耗时直接加在帧周期上 → `1/(0.100+0.056) ≈ 6.4 fps`（实测 6.76，吻合）。旧版 480px 编码仅几毫秒，所以这个 bug 一直潜伏，本次把重编码提到 1280px 才暴露。
  - **修法**：记周期起点，`sleep(max(0, interval - elapsed))`。**修复后真机复测：`video_link` = `10.00 fps / 8.69 Mbps / 单帧 106 KB`（默认档 18.14 Mbps 对照）→ 帧率满血、带宽 ≈ 默认档 48%**，正是要的"压到一半"。
  - 一键装机默认镜像已同步到 **1.2.5**（两处：nav 仓库 `4e13055`、d360_deploy `587470f`，Gitee raw 已核验）。
- **单帧重编码耗时实测（容器内真实源帧，中位 3 次）**：1920/Q80=**32.0 ms**（219 KB）；1280/Q80=**56.0 ms**（109 KB）；1280/Q65=55.6 ms；1024/Q80=47.7 ms；960/Q80=46.3 ms；960/Q70=46.0 ms；**`draft()` 无任何收益**（耗时完全相同）。
- **结论（与交接文档 §5 的旧建议相反）**：**不要靠降 `MAX_WIDTH` 救帧率** —— 贵的是 `resize()`，1920 不缩放反而最快。若要更好的画质/成本比，方向是 **`MAX_WIDTH=1920` + 降 `JPEG_QUALITY`（约 70 → 单帧 ≈150 KB ≈ 50%）**，既避免缩放开销又保住全分辨率。

## 已完成交付物（2026-09-18 上午）· 编 号 1–2 已完成，3/4/5/6 见文末「未完成」

1. ✅ **固件 1.0.21 已构建并推 ACR**（2026-09-18 上午）：`slamibot_d360_firmware:1.0.21` digest **`sha256:dc6682da842989d23f8365239f1dcc3d9f25a87d42a6eea2fbae869d306a0199`**；`Patch=21 / GIT_COMMIT=e799f1b`；版本提交 `589e7ce` 已 push `cloud`。
   - **验证**：新镜像 `install/lib/ros1_oak_ffc_sync/` 只剩 3 个二进制（`oak_h264_probe` 已消失）；oak 二进制 md5 `d9d7c6524f8c0a2b6a7fce6451d9eac9`、286472 字节，**与 1.0.16 逐字节一致**（`aceab16→28a2cc7` 的 oak 包无 diff，两者本应一致）。
   - ⚠️ **顺带发现的异常**：**1.0.17 镜像里的 oak 二进制（406528 字节 / `72d9d39a…`）对不上 1.0.16（286472 / `d9d7c652…`），尽管两者源码完全相同** → 1.0.17 那个产物本身是异常的（大概率是那轮构建踩「增量不补编 / Abandoned」留下的陈旧物）。1.0.21 已覆盖它，不影响交付，但**别再拿 1.0.17 当「已知良好基线」**。
2. ✅ **导航 1.2.4 已构建并推 ACR**（同批）：`d360_nav2d:1.2.4` digest **`sha256:d525b7f5f392ee08b603bbd5d49b8a9305481f0a07f723ef11406c83e7965dc2`**（1.2.3 保留，可回滚）。
   - 方式：**overlay**（`Dockerfile.video-link-overlay`，提交 `bf0f816`）—— 与 1.2.2/1.2.3 的交付方式一致；不做 `Dockerfile.product` 全量重编译（那步要从源码编 Python 3.11，只在早期做过一次）。COPY 目标是 **install 树**（产品镜像 install-only；701 实查只有这一份副本）。
   - **验证**：镜像内两文件 md5 与构建源逐字节一致（`4480d7fc…` / `a412fd52…`），且与 1.2.3 的（`89376122…` / `d179812b…`）不同；构建断言全过（含 `! target_ratio = 0.18`、`! /SLB_CAM_B/compressed`）+ `py_compile` + `VIDEO_LINK_OVERLAY_OK`。
3. **仍待做（需 715）**：715 换 tag 部署（`scout-nav` → `d360_nav2d:1.2.4`；固件三容器 → `1.0.21`，注意**重建 `core` 后必须 `docker restart scout-nav`**）+ 按交接文档 §5 验收。**最大风险 = CPU**（重编码 480→1280）；紧了降 `CAMERA_VIDEO_LINK_MAX_WIDTH`（1280→1024→960，**环境变量，不用重建镜像**），**不降质量下限**。
4. **验收通过后**再把 `scripts/install_2d_nav.sh` 与 `d360_deploy/nav2d/install_2d_nav.sh` 里硬编码的 `IMAGE=1.2.3`（两处）改成 `1.2.4` —— 提前改会让一键装机拉到**未验收**的镜像。
5. 另开（只报告未修）：`d360_deploy/nav2d/install_2d_nav.sh` 第 1 行是孤立 `205`。
6. 701 已清理：临时 worktree `/tmp/nav-overlay-1.2.4`、root 属主的 `/tmp/oak-1.0.1*` 均已删除；**701 导航仓库里既有的未提交改动全程未碰**（用独立 worktree 构建，容器也没动过）。

## 开始作业页三路预览卡顿的诊断（2026-09-18，未修，待用户/APP 侧决定）
- **"三路画面"其实是一张图**：APP 全仓库只有**一个** `CompressedImage` 订阅（`NativeDataCollectionSession.kt:145`），即 `/keyframe`（三相机横拼 1920×5760，Q50，`/keyframe` = **4.0 Hz / 0.39 MB/帧 / 11.2 Mbps**）；页面把这张拼接图当"全景预览"显示，"三路"就是图里三格。
- **直接原因（APP 常量）**：`KEYFRAME_THROTTLE_RATE_MS = 1_000` → 预览被节流到 **1 fps**（源是 4 Hz），所以看着就是"卡"。
- **共同链路被点云打满**：采集页点云订阅 `COLLECTION_THROTTLE_RATE_MS = 100`（10 Hz；建图页是 1000ms），而点云单帧 **867.58 KB**（实测）→ 建图中约 4–5 Hz 即 **28–35 Mbps**，与 `/keyframe` 共用同一 rosbridge/Wi-Fi 链路 → 预览帧排在后面。**预览只画 10,000 点（`MAPPING_POINTS`），却按帧传整片云**，是最大的一笔浪费。
- **修法建议（按收益排序）**：①**服务端给点云降采样**（nav 侧 `fastlio_cloud_relay` 目前是裸 relay，可换成体素降采样 → 867 KB 可降到 ~150–200 KB）＝真正的带宽解药；②APP `KEYFRAME_THROTTLE_RATE_MS` 1000 → ~250（预览 1→4 fps，需①腾出带宽才能负担）；③APP 预览解码加 `BitmapFactory.Options.inSampleSize=2` + `RGB_565`（5760×1200 的 Bitmap 是 27 MB，明显 GC 抖动）。
- 注意：这条与刚修好的**导航页视频链路是两回事**（那条走 HTTP MJPEG + 服务端压缩，已 10 fps）。

## 产品线与"视频/坐标都卡"的彻底解法（2026-09-18 用户提出新要求）
- **产品线**：**基础款**=只有 3D 空间重建，**仅三个容器**（core / firmware-sensors / ota_web），**无导航容器、无语音**；**导航款**=基础款 + `scout-nav` + 语音。
- **用户新要求**：彻底解决"视频卡 + 坐标卡"；**预览视频拉到 10 FPS**；**不影响 3D 空间重建**。
- **根因（与用户当年的现场结论一致）**：**图片、点云、位姿全挤在同一条 rosbridge WebSocket (9090)** → 大图帧造成 **TCP 队头阻塞**，位姿被排在图片后面 → **坐标延迟 2–3 秒**。当年把预览节流到 1 fps 是为绕开它。
- **解法原则**：**把预览视频从 rosbridge 上搬走**（独立 HTTP/TCP 连接）→ 坐标永不被图片阻塞，视频就能放心跑 10 fps；**重建不受影响**（重建走 PCD，`/keyframe` 只是派生预览；固件侧实测除 SystemMonitor 数频率外无其它消费者）。
- **放哪一侧**：必须放**固件侧**（基础款没有导航容器 → 不能复用 nav 的 MJPEG 端点），一个端点同时服务两款。
- **两条实现路线**（待用户选）：
  - **A（推荐）宿主 JPEG 重编码 + HTTP MJPEG**：新端点订阅 `/keyframe`（容器内 ROS 直连，不走 rosbridge），用容器里已有的 **cv2** 以 `IMREAD_REDUCED_COLOR_2/4`（DCT 域降采样，快数倍）解到 2880×600/1440×300 再编码 → 10 fps 约 4–8 Mbps，CPU ~0.3–0.6 核（仅预览打开时）。**OAK 编码器仍只用 3 个，零压力**；APP 可直接复用已验证的 `MjpegStreamClient`。
  - **B OAK H.264 单档（不要 3 档）**：0 宿主 CPU、全分辨率、10 fps 约 3 Mbps；但代码是已 revert 的（git 里可恢复：固件 `054c0ee`、APP `545ef49`），且用户此前明确否过 H.264。
- **要彻底不卡还需**：点云也占同一条 socket（867 KB × 4–5 Hz = 28–35 Mbps）→ 建议同时做**服务端点云降采样**（`fastlio_cloud_relay` 现在是裸 relay）。

## 验证状态 / 禁止
- 本机：`py_compile` + 离线真实 Pillow 复算（默认 1280/Q80 ≈ 源帧 15.9%；旧 480/Q40 ≈ 2.1%；强制超预算时降级**停在 1440 而非 160**；编码耗时 1.44x，新旧同付全分辨率解码）。**未做**：仓库 pytest（本机缺 fastapi/roslibpy；镜像 install-only 不带 tests）、真机带宽/帧率/CPU。
- 禁止：改 OAK `setQuality(90)`、动 `oak_keyframe_stitcher`、新增编码器、插帧、把压缩放相机端（§6 红线）。

## 语音线（未受影响）
- livox 冷启动竞争 **P0 未修**（`sensors.launch:32` sleep 0.5 + SDK 失败不退出）；凭据已清、听感 PASS。见 `knowledge/d360-cold-boot-stability-analysis-2026-09-17.md`、`procedures/boot-stability-timeline-test-2026-09-17.md`、`evidence/voice-715-installer-test-20260917/SUMMARY.md`。

## 开始作业预览：独立 HTTP MJPEG 端点（2026-09-18，已实现并真机验收）
- **目标**（用户）：彻底解决"视频卡 + 坐标卡"，预览拉到 **10 FPS**，不影响 3D 重建。**根因**：位姿/点云/图片全挤同一条 rosbridge socket → 大图造成队头阻塞（当年节流到 1 fps 只是绕开）。
- **服务端已交付**（固件 `d07dcfa` + `e52dafa`，镜像 **1.0.23** `sha256:c2f275b0…`，已部署 715 的 `firmware-sensors`）：
  - 相机节点内嵌 **HTTP MJPEG 预览端点**：`http://<host>:5010/api/camera/preview.mjpeg`（诊断 `…/status`）。纯标准库 HTTP；用 **cv2 `IMREAD_REDUCED_COLOR_4`** 在解码阶段降采样（1920×1200 全解 17.3ms → /4 仅 7.4ms），三路 hstack 后 Q70 编码。
  - 面板顺序 **B,A,C = 左,前,右**（与 `/keyframe` 一致，APP 三格不会颠倒）；每客户端一线程只发最新帧；端口占用/缺 cv2 时优雅停用；**不动 launch、不动 OAK 编码器（仍 3/5）、不动 `/keyframe` 与拼接节点**。
  - `e52dafa` 修掉真机发现的浪费：**无客户端时不再合成**（相机节点 CPU 29.8% → **14.8%**；空闲 status 报 `fps 0.0`），首个客户端接入时立刻出帧（实测首帧 293ms 含建连）。
- **真机验收（715）**：预览 **10.04 fps / 4.65 Mbps / 单帧 56.6 KB**（原来 1 fps / 4.2 Mbps）；三路相机仍 **10.002/10.046/9.999 fps**；`/keyframe` 4.0 Hz；`/livox/lidar` 10.0 ✓ 重建输入未变。
- **APP 侧待做（另一个 AI）**：交接文档 `.ai-workspace/handoff/APP-COLLECTION-PREVIEW-HANDOFF-2026-09-18.md` —— 预览改用 `MjpegStreamClient` 拉新端点（解码后 Bitmap 仍喂现有 `keyframe` StateFlow，**UI 一行不用改**），保留 rosbridge `/keyframe` 作回退。
  ⚠️ **用户当前看到的"三路还卡"是 APP 尚未切换**（还在 rosbridge 上按 1 fps 拉），服务端已就绪。
- **尚未做（等用户点头）**：**点云降采样** —— `fastlio_cloud_relay` 现在是裸 relay，实测点云 **867 KB/帧**（建图中 4–5 Hz ≈ 28–35 Mbps）而预览只画 10,000 点；这是"坐标卡"的另一半。
- 715 版本现状（功能等价，重启后自洽）：`firmware-sensors` **1.0.23**；`core`/`ota_web` **1.0.22**；`scout-nav` **1.2.5**。compose 已指向 1.0.23。

## 收官（2026-09-18）：视频卡 + 坐标卡 全部解决 ✓
- **用户实测确认：位姿不卡顿；点云不需要降采样（② 取消）。** 本轮目标（彻底解决视频卡 + 坐标卡、预览 10 FPS、不伤重建）全部达成。
- **最终形态（均已真机验收）**：
  - 导航款·导航页视频 = 导航容器 `?profile=video_link`（`d360_nav2d:1.2.5`）→ **10.00 fps / 8.69 Mbps**（修掉了"编码耗时不从睡眠里扣"的帧节奏 bug）。
  - 开始作业预览（**两款共用**）= 固件 `1.0.23` 内嵌**独立 HTTP MJPEG**（`:5010/api/camera/preview.mjpeg`）→ **~10 fps / 4.8 Mbps / 1440×300**（面板顺序 B,A,C 与 `/keyframe` 一致）；**已从 rosbridge 搬走**（APP 提交 `5be6646` 已推送并装机）→ 位姿不再被大图队头阻塞。
  - 相机三路 10 fps、`/keyframe` ~4 Hz、`/livox/lidar` 10 Hz、重建链路**全程未改** ✓。
  - 预览空闲不空转（相机节点 CPU **29.8% → 14.8%**）。
- ✅ **stale artifacts 已清理（2026-09-18）**：
  - `d360_deploy`：删除 `etc/install_video_link_config.sh` + README 里整节 H.264 装机步骤（含版本构成表那行、指引、目录、章节号顺延），提交 **`ea3dffe`** 已推 Gitee；远端 raw 验证脚本 **404**、README 无 `video_link/H.264/5010` 残留、纯 LF。**保留了"机型→前相机位置（新机型 `CAM_A` 前/中间）"的 3 句事实说明，并明确写了"现场不需要任何配置"**（因为固件/导航的代码默认值已按新机型固化）。
  - 715 上 `/etc/slamibot/video_link.json` **已删除** ✓（`/etc/slamibot/` 现只剩 calib.json / firmware_uploads / MID360_config.json / project_log / system）。
- **仍挂起（需等有底盘时）**：`mttcan` 自加载 —— NVIDIA L4T 自带 `denylist-mttcan.conf` 黑名单，且设备上**没有任何机制显式加载它** → 每次冷启动 `can0` 不存在 → 底盘激活永远 `NONE`（这是"底盘 none"的真正上游原因）。建议把 `mttcan` 写进 `/etc/modules-load.d/` 并纳入一键装机。
- **其它遗留**：`d360_deploy/nav2d/install_2d_nav.sh` 第 1 行是孤立文本 `205`（另一仓库，只报告未修）；715 的 `core`/`ota_web` 停在 `1.0.22`（功能等价，compose 已指向 1.0.23，**下次重启自动统一**）。

## 715 免密 sudo（2026-09-18，按用户要求，为另一个 AI 进程）
- 落地方式：**drop-in 文件** `/etc/sudoers.d/010-jetson-nopasswd`（`0440 root:root`），内容一行 `jetson ALL=(ALL) NOPASSWD: ALL`。**没有改 `/etc/sudoers` 本体**。
- **安全顺序**（重要，别在远程设备上乱试 sudoers）：① 先写候选文件 → ② `visudo -c -f <候选>` 单独校验 → ③ `install -m 0440` 落盘 → ④ `visudo -c` 整体校验（`/etc/sudoers`、drop-in、README 三个文件都 `parsed OK`）→ ⑤ 当场 `sudo -n true` 验证。
- 验证：**非 TTY 会话**（`ssh` 不带 `-tt`，即另一个 AI 进程的场景，过去会报 "a terminal is required" 或 "需要密码"）现在 `sudo -n` 直接可用，`sudo -n docker ps` 正常输出。
- **回滚一条命令**：`sudo rm /etc/sudoers.d/010-jetson-nopasswd`。
- ⚠️ **出货前要想清楚**：这是要卖给客户的设备，免密 sudo 意味着任何以 `jetson` 身份运行的东西（以及任何拿到 SSH 私钥的人）直接是 root。当前 `jetson` 口令本身就是 `jetson`（弱口令、且散落在各处文档里），所以边际风险不大；但**若要收紧出货版本，应删除该文件并同时加固账号**。
- **未做**：没有把这一条加进 `d360_deploy` 一键装机（属产品安全决策，等用户拍板）；**701 也没动**（它 sudo 仍要密码，同事在那边测试）。
