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
