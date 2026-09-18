# 会话交接文档 — 2026-09-17（新会话请先读本文 + `tasks/context-checkpoint.md`）

> 本文覆盖 2026-09-16 ~ 09-17 两条工作线：**2D 导航 1.2.x 发布线**、**固件 1.0.16 发布（rosbridge 补丁入库）**，
> 以及**尚未开始**的第三条线：**相机视频流带宽/帧率改造**。

---

## 0. 设备与环境（勿再搞混）

| 名称 | 地址 | 性质 | 现状 |
|---|---|---|---|
| **701** | `jetson@192.168.31.135` | **开发设备**（DB 有 27 套真实地图） | 跑 nav `1.2.2`（ad-hoc 容器）；固件用本地 8/31 构建 `76b95d1`（tag `latest`）；core 容器内有 3 个手改 rosbridge 文件 |
| **715 = 192.168.31.164** | `jetson@192.168.31.164` | 新设备（就是本文以前叫的"164"） | 用户正在重启；跑 nav `1.2.2`；固件是 ACR 旧版（无 rosbridge 补丁）；core 容器被我手工写过 2 个补丁文件（`cbor_conversion.py`、`outgoing_message.py`，**缺第三个 `subscribe.py`**，装 1.0.16 后即弃） |
| 局域网 | 192.168.31.0/24 | 只有 .135 与 .164 开 22 端口（已扫） | 715 的摄像头不出图是另一个 AI 在查 |

**SSH 命令模板**（Windows Git Bash；`-F NUL` 在本机无效，必须用 `-F /dev/null`）：

```bash
ssh -F /dev/null -i "C:/Users/kun/.ssh/id_rsa" -o BatchMode=yes -o ConnectTimeout=10 \
    -o StrictHostKeyChecking=no jetson@192.168.31.135 '<命令>'
```

- 701 的 `sudo` 口令是 `jetson`（无免密）：`echo jetson | sudo -S -v` 先缓存。
- 容器：`core`（ROS master 11311 + rosbridge **9090** + 业务服务）、`firmware-sensors`（雷达/相机驱动）、
  `ota_web`、`scout-nav`(715) / `scout-nav-product-v1.2.2-…`(701)（导航，自己还有 rosbridge **19090**）。
- ROS 检查优先用**导航容器**执行（它能加载自定义消息类型）：`docker exec <nav容器> bash -lc 'source /opt/ros/noetic/setup.bash; source /Scout_mini_navigation/install/setup.bash; <rostopic …>'`。

---

## 1. 已完成：2D 导航 1.2.x 发布线

### 1.1 镜像（ACR `registry.cn-shanghai.aliyuncs.com/slamibot/d360_nav2d`）

| tag | config | 内容 |
|---|---|---|
| `1.2.3` | `a3c22ceb3a0b`（manifest `sha256:51c75fe4…`） | **当前发布**：1.2.2 + 剔除镜像内残留的开发地图（maps 只剩 3 个 .py + 空 api_map） |
| `1.2.2` | `3a282f35…` | 1.2.1 + 只清空 `api_map`（顶层仍残留 ~75MB 开发地图） |
| `1.2.1` | `0fc54278…` | 到点播报预热 + 缓存优先 |
| `1.2` / `1.1` | `de136a4b…` / `3124ba46…` | 1.2 建图资源修复；1.1 缺建图资源勿用 |

> 仓库**匿名可拉**（无需 docker login）。注意：ACR 的匿名 API 调用会 401，判断可拉取性只认 docker 自己的流程。
> **ACR tag 枚举**：`/v2/.../tags/list` 拿不到权限（token `access` 为空），只能用 `docker manifest inspect <tag>` 逐个确认。

### 1.2 源码

- `Scout_mini_navigation`（GitHub `kunkunwei/…`，私有）：**远端只剩 `master` = `1ad7809`**（由 `140f049` 快进）；
  删掉的 7 个分支的提交点记录在 `tasks/branch-cleanup-2026-09-16.md`。
  关键提交：`9543415` 清地图残留 + gitignore、`33a6cae` 删 test4 + 文档改指运行时地图根、`f939ddf` 安装脚本默认 1.2.3、`1ad7809` 补 `.gitattributes`。
- **Gitee `d360_deploy`（公开）**：commit `3780b6b`，新增 `nav2d/install_2d_nav.sh`（可选 2D 导航安装脚本，默认镜像 1.2.3）+ `README.md`；
  `setup_env.bash` / `docker-compose.yml` / `udev_rules/` **一字未改**，基础一键流程行为不变。
  已用匿名 raw 实测：`https://gitee.com/electech6/d360_deploy/raw/master/nav2d/install_2d_nav.sh` → 200、0 个 CR、`bash -n` 通过。
- `D360装机流程.txt`（工作区）：§12.2 取脚本地址改为上面的 Gitee 链接（原私有 GitHub 链接新设备拉不到）。

### 1.3 701 现场

- 导航容器 1.2.1 → 1.2.2（`scout-nav-product-v1.2.2-b2cfd1b-test-20260916`）；**DB 27 套真实地图、0 断链、0 开发残留**。
- 我一度误把镜像里的 7 张开发地图（carto_map/clear_map/dinggu7_1~5）拷进设备并让 DB 改指设备路径——**已全部撤销**（文件 + 7 条 Map 行）。
- `db/backups/` 已清空；我建的 rollback 容器已删。

---

## 2. 已完成：固件 1.0.16（rosbridge 补丁入库 + 真编译 + 发布）

### 2.1 根因（务必记住）

`rosbridge_library/capabilities/subscribe.py` **原版**第 120 行：

```python
if compression == "cbor-raw":      # stock：只要客户端用 cbor-raw 就强制成通配类型
    msg_type = "__AnyMsg"
```

→ 话题被登记成 `*`：**APP（cbor-raw）拿不到可解析数据，WEB（带 type 的 cbor 订阅）被直接拒绝**，两边都看不到 3D 点云。
701 一直正常，是因为它 core 容器里这行被手改为 `... and not msg_type`（同批还有两个文件），**而任何镜像里都没有**。
（我最初误判为"APP 订阅不带 type"，已更正；APP 不需要改。详见 `known-issues/rosbridge-untyped-subscribe-poisons-topic-2026-09-16.md`。）

### 2.2 三个补丁（已入库 `rosbridge_patch/`）

| 文件 | sha256（前 16） | 作用 |
|---|---|---|
| `subscribe.py` | `ec3e4acc4b31d33b` | cbor-raw 不再强制 AnyMsg（**主因**） |
| `cbor_conversion.py` | `d0da12023c20f6ed` | 整数数组用纯 int 数组（WEB 的 JS 解码器可读） |
| `outgoing_message.py` | `8c2a79a5ca488710` | cbor-raw 返回结构化信封（APP 可解析） |
| 原始提取件 | — | `artifacts/firmware-rosbridge-cbor-patch-20260819/{stock,patched,diffs}/` |

### 2.3 发布物

| 项 | 值 |
|---|---|
| 新镜像 | `slamibot_d360_firmware:1.0.16`，manifest `sha256:c5a92d29…`，config `sha256:d5dd5f7e5c2b…` |
| `latest` | 已指向 1.0.16（同一 manifest） |
| 旧 latest 保全 | `slamibot_d360_firmware:rollback-pre-keyframe-20260831-102133`（manifest `c38b1526…`，config `71ff42d7…`） |
| 未触碰 | 固件 `1.1`/`runtime-base`/`compile`；nav2d 全部 tag |

构建方式（**真编译**，非叠加层）：`compile.bash compile patch`（catkin 6/6 包 + Cython ota_server，版本注入 1.0.15→**1.0.16**）
→ `docker build --build-arg BASE_IMAGE=...:runtime-base`（根 Dockerfile：`COPY install/` + `COPY rosbridge_patch/*` + 构建期断言）。
取证：`evidence/firmware-1.0.16-20260917/{SUMMARY.md,compile-1016.log}`。

### 2.4 源码提交

- 固件仓库 `SLAMIBOT_D360_Framework`（`/home/jetson/SLAMIBOT_D360_Framework`，分支 `main`）：
  - `aceab16 chore: bump version to 1.0.16`
  - `60560bb fix(rosbridge): 入库 cbor-raw/subscribe 补丁并在 Dockerfile 打补丁层…`
  - **已推 `cloud` 远端**（`git@github.com:kunkunwei/SLAMIBOT_D360.git`）→ `4be11c1..60560bb`
  - **`origin`（https://github.com/kunkunwei/SLAMIBOT_D360_Framework.git）推送失败**：`GnuTLS recv error (-110)` → **待重试**（或改用 SSH 远端）。
- 未提交（**别人的改动，别动**）：`src/device_service/launch/sensors.launch`(M)、`Dockerfile.keyframe-respawn`、`sbus/`、`script/`、`webrtc/`；
  另有我留下的 `Dockerfile.bak-before-rosbridge-patch-20260916`（可删，改动已在 git 历史里）。

---

## 3. 待办清单（按优先级）

### 3.1 【新任务，尚未开始】相机视频流：30fps + 降带宽

用户原话要点：
- 基础固件"开始作业的数据采集"时，**三路高清视频导致录制时 APP 显示的坐标明显延迟于现实移动**；用户在 APP 端做了相机限流才压住延迟，但**根因是画面没有压缩、带宽占用过大**。
- 目标：**APP 能看到 30 帧**，同时**降低带宽**。
- 参考：**2D 导航那边也有视频流，但"压缩得有点狠"**。
- **用户的疑问（优先回答）**：他记得相机出图**帧率被锁在 10fps**，那 2D 导航是怎么做到 **20fps** 的？

下一步动作（建议）：
1. 在 701 上量**真实数据**：`rostopic list | grep -iE "cam|oak|image|video|keyframe|SLB"` → 各话题 `rostopic type` / `hz` / `bw`（换算 Mb/s）/ 订阅者是否 `/rosbridge_websocket`。
2. 查相机节点源码与参数（`/home/jetson/SLAMIBOT_D360_Framework`，包 `ros1_oak_ffc_sync` / `oak_hardware_trigger_ros` / `oak_keyframe_stitcher` / `project_control`，以及 `src/device_service/launch/sensors.launch`）：分辨率、fps、编码（raw/JPEG/H.264）、是否有硬件编码、quality/bitrate 参数。
3. 查导航侧视频流实现（`/home/jetson/scout-nav-product-build`：搜 `mjpeg|h264|rtsp|webrtc|video|compressed`，历史线索见提交/分支名含 `video-link-stream-20260904`）：协议、参数、实测码率。
4. 回答"10fps vs 20fps"：要分清是**同一路流被重复/插帧**、还是**导航用了另一条编码链路（如 OAK 硬件 H.264）**、还是**触发源（timeshare 10Hz 硬同步）与编码帧率解耦**。**必须用实测数据回答，不要猜。**
5. 方案方向（待数据确认后再定）：OAK-D 芯片自带 H.264/H.265 硬编 → 30fps + 低码率；或 JPEG 质量/分辨率/抽帧调优；传输通道是否仍走 rosbridge（大图经 ws 易拥塞）。
   > ⚠️ **本节已结案（2026-09-17 深夜）**：实测确认**相机被 STM32 硬触发锁死 10 fps**（不是软件问题）；「OAK 硬编 H.264」这条路**试过并被否决**（OAK 仅 5 个编码器，三路 MJPEG 供 `/keyframe` 不可牺牲），固件侧相关代码已 revert。
   > **最终落地**：导航侧 MJPEG 压缩放宽到 50%（`capture.py`）→ 见 `.ai-workspace/handoff/MJPEG-VIDEO-LINK-TUNE-50PCT-HANDOFF-2026-09-17.md`。**不要再按本节去实现 H.264。**

### 3.2 715 验收（用户正在重启设备）

- 换固件到 **1.0.16**（把 compose 里 `core`/`firmware-sensors`/`ota_web` 的 image 换成 `…:1.0.16` 或 `latest`，`docker compose up -d`）。
- 验收标准（APP 与 WEB 同时在线）：
  1. core 的 rosbridge 日志里 `already established with type *`、`AnyMsg`、`is not a valid type string` **三项全 0**；
  2. 我的探针 `python repro_ws_probe.py --url ws://192.168.31.164:9090 --compression cbor` **能持续收到点云**；
  3. APP 与 WEB 都能看到 3D 点云。
- 工具与证据：`.ai-workspace/handoff/rosbridge-cbor-raw-anymsg-20260916/`（`repro_ws_probe.py`、`verify_on_device.sh`、`evidence/`）。

### 3.3 其它未决（等用户发话）

- 701 / 715 是否切换到 nav **1.2.3**（功能与 1.2.2 一致，仅少 ~75MB 死文件）。
- ACR 上**坏的 nav `1.1` tag** 是否删除。
- 701 上 **12 个历史 stopped 测试容器**是否清理。
- 715 的**相机不出图**（另一个 AI 在查）、**无宿主讯飞网关 → 到点播报无声**（未部署）。
- 固件仓库 `origin` 远端推送重试（TLS 错误）。

---

## 4. 踩过的坑 / 事实清单（新会话别重复踩）

1. **设备编号**：715 = `192.168.31.164`（用户口述"新设备 164"）；701 = `.135` 是**开发设备**。
2. **rosbridge cbor-raw → 强制 AnyMsg**：见 §2.1。判断症状看 core 容器 rosbridge 日志（`/root/.ros/log/*/rosbridge_websocket-*.log`，容器内路径）。
3. **`/livox/lidar/pointcloud` 与 APP 显示无关**：APP/WEB 的 3D 点云层订阅 `/global_cloud_navigation`（`frontend/src/ros/topics.ts:14`）；
   该话题在**建图模式**由 `fastlio_cloud_relay`（只在 `fastlio_mapping.launch`）发布，**导航模式**由 `pcd_map_publisher.py` 发布（要求激活地图有 PCD + `_display.pcd`）。
4. **导航服务无 respawn**：core 里的 rosbridge 节点没有 `respawn`，`pkill` 后不会自愈；改了 core 的东西要 `docker restart core`。
   **master 重启后其它容器的 ROS 节点必须重启**（否则 `/clock` 不来）：`core → scout-nav → firmware-sensors` 依次重启。
5. **timeshare 由雷达点云路径维护**（与 RTK 无关），在宿主 `/dev/shm`；冻结时不要起相机。
6. **镜像构建坑**：`FROM sha256:<本地镜像ID>` 在 BuildKit 下会被当成 `docker.io/library/…` 去远端找 → 用本地 tag + 传统 builder，或先 `docker tag` 起个名字。
7. **`docker exec -i <c> bash -s < script` 经 SSH 传 stdin 不可靠** → 改成「本地生成脚本 → scp/cat 到设备 → 执行」，或 `docker cp` 进容器再 `docker exec bash /path`。
8. **本地生成脚本必须 LF**（Windows 的 `write_text` 会变 CRLF，导致远端 `set -u` 报 `$'\r'` 错）。
9. **`D360装机流程.txt` 是 UTF-8 + CRLF**，编辑用字节级替换（我用的 Python）；多行 `old_string` 易失败。
10. **Gitee 仓库可直接匿名 raw 验证**；GitHub 私有仓库 raw 一定 404（别据此判断"仓库不存在"）。
11. **ACR 匿名 API 会 401**，但 docker 匿名拉取正常；tag 枚举只能逐个 `docker manifest inspect`。
12. **`rosbridge` 参数面**：`/rosbridge_websocket/max_message_size=None`（无限制）、`websocket_ping_timeout=30`；core 的 rosbridge 在 9090，导航容器的在 19090。

---

## 5. 关键路径速查

| 用途 | 位置 |
|---|---|
| 排查方法论（**建议先读**） | `.ai-workspace/knowledge/troubleshooting-playbook-2026-09-17.md` |
| 工作区事实源 | `.ai-workspace/facts/*.yaml` |
| 压缩检查点（**先读这个**） | `.ai-workspace/tasks/context-checkpoint.md` |
| 本会话任务记录 | `.ai-workspace/tasks/current.md` 末尾几条 + `branch-cleanup-2026-09-16.md`、`install-2d-nav-script-public-repo-2026-09-16.md` |
| rosbridge 问题（含更正） | `.ai-workspace/known-issues/rosbridge-untyped-subscribe-poisons-topic-2026-09-16.md` |
| APP/WEB 点云取证包 | `.ai-workspace/handoff/rosbridge-cbor-raw-anymsg-20260916/` |
| 固件 1.0.16 取证 | `evidence/firmware-1.0.16-20260917/` |
| 固件源码（701） | `/home/jetson/SLAMIBOT_D360_Framework` |
| 导航源码（701） | `/home/jetson/scout-nav-product-build` |
| 装机文档 | `D360装机流程.txt`（§12 = 2D 导航套餐） |
| 基础装机公开仓库 | `https://gitee.com/electech6/d360_deploy`（`setup_env.bash` = 基础；`nav2d/install_2d_nav.sh` = 可选 2D 导航） |
