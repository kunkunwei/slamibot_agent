# Context Checkpoint — 2026-09-18 夜：D360S ROS2 本地改造（foxglove+CBOR 替换 rosbridge JSON；清理 SCAN/云台）

> 任务记录：`tasks/current.md` 顶部 `TASK-2026-09-18-ROS2-FOXGLOVE-CBOR`
> ⚠️ 本文件曾被两个 AI 并发写过；改动前先重读全文，别只追加。

## 刚完成（2026-09-18 22:53 起，纯本地，未碰任何设备）
- ✅ 分支判定：ROS2 迁移源码 = Gitee `electech6/SLAMIBOT_D360_Framework` 的 **`codex/d360s-ros2-product-runtime`**（HEAD `8a81fe8`，**不是 main**）→ 克隆到 `F:\SLAMIBOT_D360_Framework_ros2`；开发分支 `codex/d360s-foxglove-cbor`，提交 **`8e83f1c`**；`F:\SLAMIBOT_D360_Framework`（GitHub ROS1 镜像）未动。
- ✅ **已推送 Gitee**：`codex/d360s-foxglove-cbor`（远端 = 本地 `8e83f1c`）；`main`（`2924202`）与 `codex/d360s-ros2-product-runtime`（`8a81fe8`）未被触碰；origin 推送地址改 SSH，拉取仍 HTTPS。
- ✅ 服务端：改装 `ros-humble-foxglove-bridge`；新增 `autostart_scripts/foxglove.service`（`ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=9090`，沿用 9090）；`runtime.bash` 的 SERVICES/探活/进程白名单切换；`rosbridge.service` 留作回滚入口。
- ✅ 前端：新增 `tools/foxglove-shim`（roslib 兼容层，Foxglove WS + CDR 解码）+ 产物 `ota_server/web_page/static/modules/foxglove-roslib.js`（95.4 KB，入库）；`/SLB_CAM_*/compressed` 改 Blob 直显；删 `roslib.min.js`。
- ✅ 清理：删 SCAN 页 `web_page/` 与云台整包 `src/gimbal_control/`；清 `enable_gimbal`、`ttyGimbal` udev 规则、`svc_survey` 处理、`#pryPublished`、README 表述。
- ✅ 验证：`npm test` 对 mock Foxglove 桥 **8/8 PASS**（订阅/CDR 解码/服务往返/参数读取/节流/重连）；`py_compile`、`bash -n`、`node --check`、`git diff --check` 全 PASS。

## 关键技术事实（别再重摸）
- ROS2 侧**原本完全没有 CBOR**；CBOR 仅在 ROS1 侧（固件 `60560bb` 的 rosbridge cbor-raw 补丁 + APP 点云/栅格图 `compression=cbor-raw`）。
- ROS2 的 foxglove_bridge 已迁到 **`foxglove/foxglove-sdk`**（`ros-foxglove-bridge` 只剩 ROS1）；apt 包 `ros-$ROS_DISTRO-foxglove-bridge` 可用。
- **CDR schema 坑**：foxglove_bridge 用 `====` 分隔定义，前导分隔行会被 `@foxglove/rosmsg` 解成空根定义 → 必须剥前导分隔行并过滤空定义，否则每帧解成 `{}`。
- **`@foxglove/ws-protocol@0.8.0` 自带 server 不派发 `serviceCallRequest`**（客户端按规范的 35 字节帧它收到了却不 emit）→ 测试 fixture 改为按协议规范手写 mock 桥。
- Foxglove 协议的**服务调用仍是 JSON**（低频可接受）；高频面（图像/状态）走二进制 CDR。
- 页面仍有两处 `JSON.parse(message.data)`：`/topic_frequencies`、`/system_monitor_history` 是 `std_msgs/String` 内嵌 JSON（发布端选择，非协议 JSON）。

## 未完成 / 下一步
1. ⏳ **真机未验证**：colcon、foxglove_bridge 启停、浏览器真实画面（重点确认 `/SLB_*` 是否被 foxglove 转码成视频、`/device_type` 参数可否读）；`--show-args` 核参数后可加白名单加固。
2. ⏳ 部署副作用：删云台 udev 规则后，真机 `provision.bash` 会重写 `/etc/udev/rules.d/99-serial-aliases.rules` 并 reload。
3. ⏳ 发现未动：`oak-camera_driver`、`oak_cam_ros2` 的 `package.xml` 声明了代码中**从未使用**的 `<depend>foxglove_msgs</depend>`（疑似早期试验残留）。
4. ⏳ 701 遗留：nav 仓 19 改+20 未跟踪改动未上云；`/keyframe` 三格面板顺序待决策；`docker_ws_backup` 8.1G 等大件未清。
5. ⏳ 小缺陷：`d360_deploy/nav2d/install_2d_nav.sh` 首行孤立 `205`；语音脚本 `crontab` 自验少 `-u`；挂起项 `mttcan` 冷启动 `can0` 缺失、4G PPP-vs-ECM 未确证。

## 新规则（2026-09-18，必须遵守）
- 「单一云端源同步规则」已写入 `core/change-policy.md`：禁止 copy / scp / 复制粘贴跨设备传源码或版本化配置——一律「改完推云端 → 其他设备 pull」；**D360/D360S 设备上禁止随意开分支、禁止另做源码备份**。同步修订 `core/git-safety.md`（分支建议限定开发机 + 设备侧规则）与 `AGENTS.md`（偏好清单加条目）。

## 验证状态 / 禁止
- 本次 **colcon / 真机 NOT RUN**；不得把「已提交」「已推送」「本地 mock PASS」当成「功能已验证」。
- 仓内容为 LF（`git ls-files --eol` → `i/lf`）；Windows 工作树因 `core.autocrlf=true` 呈 CRLF，**从工作树直接拷脚本到 Linux 仍会中毒**，一律经 git 取文件。
- 工作台主分支 3.3GiB 大文件问题仍由另一 AI 处理。
