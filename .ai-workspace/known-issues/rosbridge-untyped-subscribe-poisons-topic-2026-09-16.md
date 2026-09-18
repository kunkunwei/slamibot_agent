# 715（=192.168.31.164）WEB/APP 看不到 3D 点云：**固件 rosbridge 对 cbor-raw 强制 AnyMsg**（结论已更正）

> **2026-09-16 20:20 更正**：本文原判"APP 订阅不带 type"是**错的**。真正根因是固件里
> `rosbridge_library/capabilities/subscribe.py` 的 stock 代码：
> `if compression == "cbor-raw": msg_type = "__AnyMsg"` —— 只要客户端用 cbor-raw 订阅就把类型强制成通配，
> 与客户端带没带 type 无关。701 该文件被手改为 `... and not msg_type`，所以 701 一直正常。
> **APP 无需修改。** 更正后的完整交付包见 `.ai-workspace/handoff/rosbridge-cbor-raw-anymsg-20260916/`。


- 日期：2026-09-16
- 设备：715 = `jetson@192.168.31.164`（用户确认 715 就是 192.168.31.164，即本会话前面称的「164」）
- 结论：**不是** `/livox/lidar/pointcloud` 缺失、**不是**浏览器、**不是**没有地图。是 APP 以**无类型**方式订阅 `/global_cloud_navigation`，把话题注册成通配类型 `*`，导致 WEB 的带类型订阅被拒 / cbor 编码抛 `AnyMsg` 异常。

## 一、事实链（全部实测）

1. WEB 的 3D 点云层订阅 `/global_cloud_navigation`（`frontend/src/ros/topics.ts:14`、`Viewer3D.tsx:98`），APP 走 cbor-raw 订阅同一话题。`/livox/lidar/pointcloud` 在前后端**无任何引用**，701 上它的订阅者数为 0，发布者是雷达驱动 `livox_lidar_publisher2`（不是 `/livox_repub`，后者发 `/livox_pcl0`）。
2. 715 的 rosbridge（**core 容器**，端口 9090；导航容器自己的 rosbridge 在 19090）日志：
   - `[Client 2] Subscribed to /global_cloud_navigation`（20:01:27，与 `[Client 3] Subscribed to /map` 同秒出现，符合 APP 的两个原生会话）
   - `[ERROR] [Client 5] [id: probe] subscribe: Tried to register topic /global_cloud_navigation with type sensor_msgs/PointCloud2 but it is already established with type *`（我的带类型探针被拒）
   - 701 的同类日志计数 **0** 条。
3. 若带类型订阅先注册，之后 cbor 发送会抛：`AttributeError: 'AnyMsg' object has no attribute '_slot_types'`（`cbor_conversion.py:45`），消息被静默丢弃 → WEB 依然空白。
4. 探针验证（我本机 python websocket 客户端）：
   - 715：`cbor` → 0 条（被拒）；`cbor-raw` → 正常 26~33 条
   - 701：`cbor` → 37 条/12s；`cbor-raw` → 正常
5. `/clock 200Hz`、timeshare 10Hz、雷达 `/livox/lidar 10Hz`、建图态 `/global_cloud_navigation 10.000Hz` 全部正常。

## 二、APP 侧为什么也不显示（与 701 的补丁有关）

ACR 镜像里的 rosbridge 是**原版**，`cbor-raw` 返回 `{secs,nsecs,bytes}` 信封；而 APP「请求 cbor-raw、却按 cbor 结构化信封解析」→ 解析失败 → 不渲染。
701 的 **core 容器可写层**里有两个 2026-08-19 的手改文件（**任何镜像里都没有**）：

| 文件 | 原版 | 701 手改 |
|---|---|---|
| `rosbridge_library/internal/cbor_conversion.py` | 整数数组编成 IETF typed-array tag（byte string） | 改成纯 int 数组（JS 端可解析） |
| `rosbridge_library/internal/outgoing_message.py` | `cbor-raw` → `{secs,nsecs,bytes}` | `cbor-raw` → 复用 `get_cbor` 的结构化信封 |

sha256：原版 `c46385005085faa3…` / `17355d0a129a838f…`；701 手改 `d0da12023c20f6ed…` / `8c2a79a5ca488710…`
（提取件：`artifacts/firmware-rosbridge-cbor-patch-20260819/{stock,patched,diffs}/`）

注意：手改后的 `cbor-raw` 也走 `get_cbor`，所以在话题被 `*` 毒化时它**同样会抛 AnyMsg**——补丁不能替代"不带类型订阅"的修复。

## 三、本次在 715 上做过什么（可回滚）

- 备份原文件：容器内 `/root/.codex-backup/rosbridge-cbor-20260916-195249/`（原版两个文件）。
- 写入 701 的两个补丁文件，sha256 与 701 一致。
- 为清掉 `*` 注册重启过 rosbridge（该话题的 roslaunch 节点**没有 respawn**，手工 kill 后不会自愈，一度导致 9090 中断）。
- 已恢复：`docker restart core`（rosbridge 归 roslaunch 托管）→ `docker restart scout-nav` → `docker restart firmware-sensors`（master 重启后其它容器的 ROS 节点需重启，否则 `/clock` 不来）。
- 当前状态：`/clock 200.144Hz`、建图中、`/global_cloud_navigation 10.000Hz`、core rosbridge `AnyMsg=0`。
- 验收探针仍为 0 条 → 被 APP 的 `*` 注册拒绝（见一.2）。

## 四、待修 / 建议

1. **APP 侧（根因）**：点云订阅必须带 `type: sensor_msgs/PointCloud2`。APP 为今天 14:29 安装的 debug 包 `com.example.metacam.debug` v1.6.5-debug；701 历史上 0 条该错误，怀疑是本次 APP 改动引入。APP 日志：`NativePointCloud: Point-cloud subscribe (cbor-raw, throttle=0ms, queue=1)`（无 type）。
2. **固件侧**：把两个补丁打进镜像并推 ACR（新 tag + 更新 latest），解决 WEB 的 typed-array 解析与 APP 的 cbor-raw 信封形状。**但在 APP 修好之前，715 的 WEB 仍会被拒。**
3. 复现命令（本机）：`python tmp/ws_probe2.py ws://<设备>:9090 cbor sensor_msgs/PointCloud2 10`。

---

## 五、已在镜像层修复（2026-09-17）

**根因确认（第三处补丁，决定性的那处）**：`rosbridge_library/capabilities/subscribe.py` 原版第 120 行
`if compression == "cbor-raw": msg_type = "__AnyMsg"` —— 只要客户端用 cbor-raw（APP 的做法）就无条件把类型改成通配，
与客户端带没带 type 无关。701 该行被手改为 `... and not msg_type`，所以 701 一直正常。

**处置**：把 2026-08-19 现场手改的三个文件**入库并写进构建**（原先只在 701 的 core 容器可写层，任何镜像都没有）：

| 文件 | sha256（前 16） | 作用 |
|---|---|---|
| `rosbridge_patch/subscribe.py` | `ec3e4acc4b31d33b` | cbor-raw 不再强制 AnyMsg（**本条是主因**） |
| `rosbridge_patch/cbor_conversion.py` | `d0da12023c20f6ed` | 整数数组用纯 int 数组（WEB 的 JS 解码器可读） |
| `rosbridge_patch/outgoing_message.py` | `8c2a79a5ca488710` | cbor-raw 返回与 cbor 相同的结构化信封（APP 可解析） |

- 源码改动：`SLAMIBOT_D360_Framework` 新增 `rosbridge_patch/`，根 `Dockerfile` 追加 COPY + 构建期断言（`ROSBRIDGE_PATCH_OK`）；
- **真编译**：`compile.bash compile patch`（catkin 6 包全过 + Cython），版本注入 **1.0.15 → 1.0.16**；
- 镜像：`slamibot_d360_firmware:1.0.16`，manifest `sha256:c5a92d29…`，config `sha256:d5dd5f7e5c2b…`；
- 发布：`1.0.16` 已推送，`latest` 指向它；**旧 latest 用 `rollback-pre-keyframe-20260831-102133` 保住**（config `71ff42d7…`）；
  `1.1` / `runtime-base` / `compile` 未动。

> 旧 latest（`71ff42d7`，8 周前那版）已在推送前用名字保住，可随时回退。
