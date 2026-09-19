# Context Checkpoint — 2026-09-19 凌晨：D360 前后端链路换 Foxglove 二进制（代码已改完并推云端，未部署）

> 任务记录：`tasks/d360-foxglove-link-2026-09-19.md`（完整）；`tasks/current.md` 顶部有指针
> ⚠️ 本文件曾被两个 AI 并发写过；改动前先重读全文，别只追加。

## 刚完成（纯本地改码 + 推云端；未碰任何设备）
- **固件仓** `F:\SLAMIBOT_D360_Framework`：本地已 ff 到云端 `87c966f`(1.0.23)；新分支 `codex/d360-foxglove-link-20260919`（`a7037a7` + 收尾 `5b22847`），已推 github `kunkunwei/SLAMIBOT_D360`；`main` 未动。
  - `core.launch`：rosbridge include → `foxglove_bridge.launch port:=9090`（**同端口，无第二端口/无开关**）；`Dockerfile` 加 `ros-noetic-foxglove-bridge` 层、删补丁层；删 `rosbridge_patch/`（3 文件 449 行）。
  - 新增 `tools/foxglove-shim/`（ROS1 版，源自 D360S 的 551 行 shim，**只改 3 处**：`MessageReader` 换 `@foxglove/rosmsg-serialization`、通道判定 `encoding==="ros1"`、`parse(schema,{ros2:false})`）；产物 `ota_server/web_page/static/modules/foxglove-roslib.js`(78,887 B) 入库；删 `roslib.min.js`。
  - `main.js`：`/keyframe` 改二进制 Blob（不再 base64 data-URL）；`/project_image` 只留字节路径。收尾提交：`.gitignore` 放行 shim 的 `package.json`/lock、`.dockerignore` 排除 `tools/`、AGENTS/CLAUDE/OTA.md/setting_server 注释同步 Foxglove。
  - 验证（主代理亲跑）：shim `npm test` **8/8 PASS**；`node --check`、`git diff --check` PASS。
- **导航仓** `F:\d360_nav2D`（权威基线 `4e13055`＝用户指定的「最新提交」）：新 worktree `F:\d360_nav2D-foxglove`，分支 `codex/foxglove-link-20260919`（`720a5fc`），已推 github `kunkunwei/Scout_mini_navigation`；`master`(4e13055) 与两个既有 worktree（`F:\d360_nav2D` 的 f281b8e + 2 个地图改动、`tmp/nav-50pct`）均未动。
  - `frontend/vendor/foxglove-roslib/index.js`＝vendored 单文件 shim（源 `SLAMIBOT_D360@5b22847`）。**曾走 submodule 已废弃**：整仓 72MB 进前端目录，且会让 `publish-navigation-ui` CI 与镜像构建（未开 submodules）直接失败。
  - `rosClient.ts` 换 shim（删无调用方的 `publish`）；连接直连 `ws://<host>:9090`；删 nginx `/rosbridge` 与 dev 代理；`package.json` 加 3 个 `@foxglove/*`、移除 `roslib`/`@types/roslib`。
  - 验证（主代理亲跑）：`npm run build` ✓、`npm run build:package` exit 0、`vitest` 3 failed/45 passed 文件、7 failed/153 passed 用例；7 个失败全在 `normalizeMaps`/`DashboardPage`/`ModePanel`，与本次 diff 无关（既有失败）。

## 关键技术事实（别再重摸）
- ROS1 foxglove_bridge：通道编码 **`ros1`（原生 ROS1 二进制）**、schema 是 ROS1 `.msg` 全文、**服务调用仍 JSON**、客户端发布只收 `ros1`；**ROS1 侧不存在「foxglove+CBOR」**，CBOR 只活在这次删掉的 rosbridge 补丁里。noetic 有二进制包 0.8.4-1（上游建议 ROS1 从源码构建 0.8.5）。
- 视频早就不在 WS 上：固件 1.0.21~1.0.23 把 HTTP MJPEG 内置进相机节点（默认 `~preview_port=5010`、`/api/camera/preview.mjpeg`、无客户端不合成）；APP `RobotEndpoint.kt:36` 已用它。**用户明确禁止本次使用 5010**，故 5001 控制台仍订阅 `/keyframe`（现在是二进制，不再 base64）。
- 产品分层：基础款＝固件仓（core/firmware-sensors/ota_web，3D 重建由 base 自己 `roslaunch faster_lio`）；2D 导航＝外挂容器；**固件仓对导航引用 0 处**，依赖方向只有 nav→base，桥只落 base。
- 残留风险：`src/device_service/launch/project_control.launch` 仍 include rosbridge（用户要求保留、上机测试后再定），而 `.codex/AGENTS.md`/`.claude/CLAUDE.md` 仍写它是「生产环境入口」；若真按它启动，rosbridge 会占 9090 且与页面协议不兼容。

## 未完成 / 下一步
1. ⏳ **未部署、未真机验证**：等用户上班在 701 编译/部署测试；Docker 未构建（`ros-noetic-foxglove-bridge` 在 runtime-base 上的可装性未实测）。
2. ⏳ APP 未改（用户明确后续单独改）；导航 SPA 已改但未真机联调。
3. ⏳ 切到 Foxglove 后，旧 APP/旧 SPA 在 D360 上不可用属**预期**，不算验收失败。
4. ⏳ 未决：两条 MJPEG（base 5010 vs 导航 5000）是否以 5010 收口；shim 单一来源的最终形态（vendored vs 独立仓+npm 依赖）。

## 第二轮追加（2026-09-19，用户追问后）
- 固件仓 `d29014b`（已推送）：删 `project_control.launch` + `.codex/AGENTS.md`/`.claude/CLAUDE.md`/`docs/debug_guide.md` 同步 compose 真实入口。
- 导航仓 `29b7482`（已推送）：删 `compression`/`queueLength` 死参数（rosbridge 专有），只留仍生效的 `throttleRate`。
- 陈旧测试证据：3 个失败测试文件停在 `6dfbbbc`(08-09)，对应实现已推进到 08-19/08-25/09-04；在基线 `4e13055` 上跑同样 3 个文件 → 同样 7 条失败、同样报错。
- 仍未决：视频链路方向（HTTP MJPEG vs H.264）与两条 MJPEG 收口（base `:5010` / 导航 `:5000`）。

## 验证状态 / 禁止
- 本次 **colcon/colcon 无关、Docker/真机 NOT RUN**；不得把「已提交」「已推送」「mock/单测 PASS」「构建 PASS」当成「功能已验证」。
- 未合并任何分支、未 force push、未改历史、未动设备。
