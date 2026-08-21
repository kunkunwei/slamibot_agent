---
id: app-map-cbor-rosbridge-2026-08-19
title: D360 Android APP 点位管理右半屏不显示 /map（CBOR 订阅链路）— 未完全修复
date: 2026-08-19
status: PARTIAL_FIX_APPLIED
scope: read-only analysis + live container patches (not yet persisted)
related_repos:
  - SLAMIBotApp   # Android APP, 只读未改
  - d360_nav2D    # FastAPI/Nginx/前端只读
  - SLAMIBOT_D360_Framework  # core 容器 rosbridge 启动来源
related_known_issues:
  - web-app-map-display-2026-08-18.md
  - scout-nav-troubleshoot-2026-08-18.md
  - board-rosbridge-port-conflict-2026-08-19   # memory
  - board-bashrc-dead-proxy                    # memory
---

# D360 Android APP 点位管理右半屏"等待/map栅格"——CBOR 订阅链路诊断与 live patch（未持久化）

> 报告人：Claude（EXPLORER + 实施 live patch）
> 接手人：另一位 dev agent（请先阅读本文件 §0-§3 决定是否继续 §4 后续）

---

## 0. 现象复述

- 用户原话：导航控制 → 点位管理 → 地图列表可正常切换；右半屏显示 "等待/map栅格"。
- Web 端（`http://192.168.31.135/app/`）显示地图正常。
- 涉及机器人：D360（松灵 Scout mini + Livox Mid-360）
- APP 仓库：`F:\SLAMIBotApp\app\app\src\main\java\com\example\metacam\`
  - 关键文件：`NativeOccupancyGridClient.kt`、`D360Topics.kt`、`NativeNavigationSession.kt`、`RobotEndpoint.kt`、`NativeNavigationPages.kt`

---

## 1. 事实速览（板上 2026-08-19 实测）

| 维度 | 值 |
|---|---|
| Jetson SSH | `ssh jetson@192.168.31.135`（默认 22 端口，密钥免密） |
| ROS Master | `http://127.0.0.1:11311`（宿主机，host network 共享） |
| 9090 rosbridge | `core` 容器，`PID 17668`，启动命令 `roslaunch rosbridge_server rosbridge_websocket.launch` |
| 9090 rosbridge 源码目录 | `/opt/ros/noetic/lib/python3/dist-packages/rosbridge_library/` |
| 19090 rosbridge | `scout-nav` 容器，FastAPI/nav_api 内部用，APP 不连 |
| 板上 LAN IP | `192.168.31.135`（用户手动把 APP 端 host 改成了这个） |
| APP 端 host 默认 | `192.168.117.6`（热点 IP），但用户已覆盖为 `192.168.31.135` |
| APP 端 rosbridge port | `9090`（`RobotEndpoint.kt:31`） |
| APP 订阅方式 | `compression: "cbor-raw"`，自定义 CBOR 二进制解析器 |
| `/map` topic | `nav_msgs/OccupancyGrid`，由 `/map_server` 发布 |
| nginx 反代 | `/rosbridge` → `127.0.0.1:9090`（web 走这条） |

---

## 2. 根因：3 个串联 bug 全部在板端 rosbridge 实现里

APP 的 `NativeOccupancyGridClient.kt` 写的是：
- 订阅 flag：`compression: "cbor-raw"`
- 解析器：自定义 CBOR 解码器，**期望 `msg.{header, info, data}` 三个键、`info.width/height/resolution/origin`、`data` 是 plain CBOR array of int8**

但板上 9090 的 rosbridge 实际行为不匹配，三处 bug：

### Bug A — 订阅类型被强制覆盖（`subscribe.py:120-121`）

```python
# 原代码
if compression == "cbor-raw":
    msg_type = "__AnyMsg"
manager.subscribe(self.client_id, self.topic, self.on_msg, msg_type)
```

`compression == "cbor-raw"` 时，rosbridge 强制把 `msg_type` 设为 `__AnyMsg`，但 `/map` 实际是 `nav_msgs/OccupancyGrid`。订阅类型不匹配，**0 帧到达**（实测）。

### Bug B — `cbor-raw` 输出的信封不是 APP 解析器期望的结构（`outgoing_message.py:40-49`）

```python
# 原代码
def get_cbor_raw(self, outgoing_msg):
    if self._cbor_raw_msg is None:
        now = get_rostime()
        outgoing_msg[u"msg"] = {
            u"secs": now.secs, u"nsecs": now.nsecs,
            u"bytes": self._message._buff
        }
        self._cbor_raw_msg = encode_cbor(outgoing_msg)
    return self._cbor_raw_msg
```

`cbor-raw` 输出 `{op, topic, msg: {secs, nsecs, bytes}}`，但 APP 解析器期望 `{op, topic, msg: {header, info, data}}`（这是 `compression=cbor` 的结构）。

### Bug C — typed array 被包成 CBOR Tag 而非 plain array（`cbor_conversion.py:86-90`）

```python
# 原代码
elif slot_type in TAGGED_ARRAY_FORMATS:
    tag, fmt = TAGGED_ARRAY_FORMATS[slot_type]
    fmt_to_length = fmt.format(len(val))
    packed = struct.pack(fmt_to_length, *val)
    out[slot] = Tag(tag=tag, value=packed)   # ← CBOR Tag 72/77/78...
```

`int8[]`（OccupancyGrid.data）被编为 `Tag(72, packed_bytes)`（IETF typed-array tag）。APP 的 `readInt8Array()` 只接受 plain `CBOR_MT_ARRAY`，遇到 Tag 静默 return null，UI 不更新。

---

## 3. 已应用的 live patch（3 个）

⚠️ **这些 patch 写在 core 容器文件系统里，容器重启即失效。需要按 §6 落到镜像里。**

执行时间：2026-08-19 15:20 - 15:28 CST
执行位置：`jetson@192.168.31.135` → `docker exec core ...`
备份目录（容器内）：`/root/.ros/patches_20260819/{subscribe,outgoing_message}.py.orig`
备份缺失：`cbor_conversion.py.orig` 未备份（补丁时遗漏）

### Patch 1: `subscribe.py`（fix Bug A）

```diff
@@ capabilities/subscribe.py line 120-121 @@
-        if compression == "cbor-raw":
+        if compression == "cbor-raw" and not msg_type:
             msg_type = "__AnyMsg"
```

效果：客户端传了 `type` 时（如 APP 传 `nav_msgs/OccupancyGrid`），订阅类型被尊重。

### Patch 2: `outgoing_message.py`（fix Bug B）

```diff
@@ internal/outgoing_message.py line 40-49 @@
     def get_cbor_raw(self, outgoing_msg):
-        if self._cbor_raw_msg is None:
-            now = get_rostime()
-            outgoing_msg[u"msg"] = {
-                u"secs": now.secs,
-                u"nsecs": now.nsecs,
-                u"bytes": self._message._buff
-            }
-            self._cbor_raw_msg = encode_cbor(outgoing_msg)
-
-        return self._cbor_raw_msg
+        # 2026-08-19 patch: client APP requests cbor-raw but parses cbor envelope.
+        return self.get_cbor(outgoing_msg)
```

效果：`cbor-raw` 与 `cbor` 输出结构一致。**注意**：会让"裸消息字节流"的 cbor-raw 用法全部失效（如果未来引入其他客户端用 cbor-raw 期望 bytes blob，需要再讨论）。

### Patch 3: `cbor_conversion.py`（fix Bug C）

```diff
@@ internal/cbor_conversion.py line 86-90 @@
         # numeric arrays
         elif slot_type in TAGGED_ARRAY_FORMATS:
-            tag, fmt = TAGGED_ARRAY_FORMATS[slot_type]
-            fmt_to_length = fmt.format(len(val))
-            packed = struct.pack(fmt_to_length, *val)
-            out[slot] = Tag(tag=tag, value=packed)
+            # 2026-08-19 patch: 客户端 APP 期望 CBOR array of int，而不是
+            # IETF typed-array tag (Tag 72/77/...) 包裹的 byte string。
+            out[slot] = [int(x) for x in val]
```

效果：所有 typed array 编码为 plain CBOR array of int，APP 解析器可读。
**注意**：会增大所有 typed array 消息体积（如 `float32[]` 点云会膨胀数倍）。当前只 APP 用 CBOR，影响有限。

### 文件 MD5 状态

| 文件 | MD5（patched） | 原 MD5 |
|---|---|---|
| `capabilities/subscribe.py` | `8121e976eb99ea50a7ad8c73a2fabed6` | `33b18f4034669c55115e773f68001d47` |
| `internal/outgoing_message.py` | `e9574d2322cd6fb662aff427f56becef` | `be7c114b1549775454f9ee7c4148ee34` |
| `internal/cbor_conversion.py` | `ed958e0b16486a804503f1116355194c` | （未记录原值，备份缺失） |

---

## 4. 验证结果

### 4.1 修复前（对照）

`cd F:/slamibot_agent/tmp && python ws_probe.py`

| 订阅 | 结果 |
|---|---|
| `compression: cbor-raw` | 0 binary frames（订阅失败） |
| 无 compression（JSON） | 1 text frame, 3.83 MB |

### 4.2 修复后（3 patch + 重启后）

| 订阅 | 结果 |
|---|---|
| `compression: cbor-raw` | **1 binary frame, 56,573 bytes** ✓ |
| 无 compression（JSON） | 1 text frame, 169 KB（说明 /map 仍在更新） |

### 4.3 CBOR 结构核对（python `cbor` 库解码）

```python
top-level keys: ['op', 'topic', 'msg']
  op   = 'publish'
  topic= '/map'
  msg keys: ['header', 'info', 'data']
    info.width=227  info.height=248  resolution=0.05000000074505806
    info.origin.position.x=-6.692
    data length: 56296          ← 与 227×248 一致 ✓
    header keys: ['seq', 'stamp', 'frame_id']
```

结构上**完全匹配** APP `NativeOccupancyGridClient.kt:173-296` 的 `parseCborOccupancyGrid` 预期。

### 4.4 重启后 rosbridge 状态

```
core 容器 rosbridge：PID 17668（15:28:48 起）
日志末段（节选）：
  [rosout] Rosbridge WebSocket server started at ws://0.0.0.0:9090
  [rosout] [Client 0] Subscribed to /map
  [rosout] [Client 3] Subscribed to /map
  topic[/map] adding connection to /map_server
```

APP 端确实**已重新订阅** `/map`，`/map_server` 也推送到了 rosbridge。链路通。

### 4.5 APP UI 仍然"等待/map栅格"

**用户 15:35 反馈：APP 切换地图后右半屏仍显示占位文字。**

⚠️ 意味着 3 个 patch 修了"rosbridge → 9090"链路，但 APP 侧仍有未定位的问题（见 §5）。

---

## 5. 接手人调查方向（重要！）

APP 仍不显示地图。可能原因排序：

### 假设 1（最可能）：APP 端的 CBOR 解析器还有未覆盖的格式差异

`NativeOccupancyGridClient.kt:173-296` 是手写 CBOR 解码器。已知能解析：op/topic/msg、header、info.width/height/resolution/origin、data 数组。

未覆盖/可能出错的字段：
- `info.load_map` / `info.map_load_time` —— 解析器有 `else -> mc.skipValue()`，应当 OK
- `header.stamp.secs/nsecs` —— 同上，skip
- `header.frame_id` —— 同上
- **data 字段里 int 的 CBOR 编码范围**：APP 只接受 `CBOR_MT_UINT` 与 `CBOR_MT_NINT`，但 python 的 `cbor` 库对负数（如 -1=unknown）会编成 NINT 吗？需要**真机抓 raw bytes 看 data 区域**。建议：
  ```python
  # 在 verify_cbor.py 里加：
  for i, item in enumerate(decoded['msg']['data'][:10]):
      print(f"  data[{i}]={item} type={type(item).__name__}")
  ```

### 假设 2：APP 没真正连上新 rosbridge

- 我重启了 9090 rosbridge，但 APP OkHttp 客户端的重连退避是 1→2→4→8→10s
- APP 端"等待/map栅格"是不是旧的占位状态没被新数据替换？
- **快速验证**：在手机上"切换地图"动作是否会触发新连接？观察 logcat 里 `OccupancyGridClient` tag 日志

### 假设 3：UI 状态没更新（数据到了，StateFlow 没推）

- `mutableOccupancyGrid.value = grid` 后 UI 没刷新（Compose 重组失败）
- 检查点：`NativeNavigationPages.kt:462-466` 的 `remember(occupancyGrid)` 是否被正确触发

### 假设 4：地图分辨率/尺寸不匹配被静默丢弃

- APP 端有 `MAX_CELLS = 10_000_000` 检查
- 当前 227×248=56,296，**远低于阈值**，不应触发
- 但如果换了大地图（如 1000×1000），可能超过

### 假设 5：APP 的 onMessage 没收到 binary frame

- 我测出 binary frame 到了，但 APP 的 `WebSocketListener.onMessage(WebSocket, ByteString)` 是否被调用？
- OkHttp 默认行为：binary frame 触发 `onMessage(ByteString)`，text frame 触发 `onMessage(String)`
- 需要 logcat 确认

### 推荐诊断步骤

```bash
# 1. ADB 抓 logcat（用 -T 限制时间戳避免 hang）
adb shell "logcat -d -T 200" | grep -iE 'OccupancyGrid|metacam.*com\.|parse|Failed|CBOR'

# 2. APP 强制重连：杀掉 APP 进程让它重启
adb shell am force-stop com.example.metacam.debug
adb shell am start -n com.example.metacam.debug/com.example.metacam.MainActivity

# 3. 重连后立刻观察新订阅是否上来
ssh jetson@192.168.31.135 'docker exec core tail -f /root/.ros/log/de636982-9b7f-11f1-9ada-00e09a2f15e6/rosbridge_websocket-1.log | grep -E "Subscribed to /map|topic\[/map\] adding"'
```

### 如果定位到 APP 端 CBOR 解析仍不工作，最简方案

APP 的 `NativeOccupancyGridClient.kt:80` 把 `compression: cbor-raw` 改成 `compression: cbor`（实测过 cbor 工作）。但用户不允许改 APP 代码，所以这个方案需要重新协商。

或者：再补一个 patch 让 `cbor-raw` 输出 **完整 envelope + data 是 plain array**（已经做）。如果还是不行，需要在 patch 里加更多 CBOR 字段格式调整。

---

## 6. 持久化（必做，否则容器重启 patch 丢）

容器 `/opt/ros/noetic/lib/python3/dist-packages/rosbridge_library/` 是镜像层。重启 core 容器 patch 全丢。

需要把 3 个 patch 落到 **core 镜像的 Dockerfile** 或 **入口脚本**（如 `entrypoint.sh`）。

### 方案 A（推荐）：写入 Dockerfile，用 `COPY` + `sed` 在 build 时打

找 `core` 镜像的 Dockerfile（推测路径：`/root/SLAMIBOT_D360_Framework/install/share/project_control/` 或 image build context），加：

```dockerfile
# Patch rosbridge_library for APP CBOR compatibility (2026-08-19)
COPY patches/rosbridge/ /opt/ros/noetic/lib/python3/dist-packages/rosbridge_library/
RUN find /opt/ros/noetic/lib/python3/dist-packages/rosbridge_library -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```

把 patched 的 3 个文件（连同 __pycache__ 清掉）放进 `patches/rosbridge/`。

### 方案 B：entrypoint.sh 打 patch 后启动

在 core 容器的 `docker-entrypoint.sh` 或 `core.launch` 启动前 sed：

```bash
# Fix rosbridge cbor-raw for APP compatibility
sed -i 's/        if compression == "cbor-raw":/        if compression == "cbor-raw" and not msg_type:/' \
    /opt/ros/noetic/lib/python3/dist-packages/rosbridge_library/capabilities/subscribe.py
# ... 其他两个 patch 类似
```

缺点：sed 在 busybox/alpine shell 可能不一样；Python in-place 编辑更稳。

### 方案 C（最简单）：用 volume mount 把 patched 文件挂进去

```bash
docker run ... -v /home/jetson/rosbridge_patches/capabilities/subscribe.py:/opt/ros/noetic/lib/python3/dist-packages/rosbridge_library/capabilities/subscribe.py:ro \
              -v /home/jetson/rosbridge_patches/internal/outgoing_message.py:/opt/ros/noetic/lib/python3/dist-packages/rosbridge_library/internal/outgoing_message.py:ro \
              -v /home/jetson/rosbridge_patches/internal/cbor_conversion.py:/opt/ros/noetic/lib/python3/dist-packages/rosbridge_library/internal/cbor_conversion.py:ro \
              ...
```

需要把 patched 文件落到 host 路径（已存在 `F:\slamibot_agent\tmp\patch_*.py` 是 patch 脚本，不是 patched 文件本身）。

---

## 7. 回滚步骤（如接手人决定撤掉 patch）

```bash
# 容器内（已备份）
ssh jetson@192.168.31.135 'docker exec core bash -lc "
  cp /root/.ros/patches_20260819/subscribe.py.orig /opt/ros/noetic/lib/python3/dist-packages/rosbridge_library/capabilities/subscribe.py
  cp /root/.ros/patches_20260819/outgoing_message.py.orig /opt/ros/noetic/lib/python3/dist-packages/rosbridge_library/internal/outgoing_message.py
  # cbor_conversion.py 没有备份，需要从上游镜像层恢复（重启容器即可）
  find /opt/ros/noetic/lib/python3/dist-packages/rosbridge_library -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
"'

# 重启 9090 rosbridge
ssh jetson@192.168.31.135 'docker exec core bash -lc "
  source /opt/ros/noetic/setup.bash && source /root/SLAMIBOT_D360_Framework/install/setup.bash
  rosnode kill /rosbridge_websocket
  sleep 4
  nohup roslaunch rosbridge_server rosbridge_websocket.launch >> /root/.ros/log/rosbridge_manual_20260819.log 2>&1 &
"'
```

---

## 8. 已用工具与脚本（落到本地）

放在 `F:\slamibot_agent\tmp\`：

| 文件 | 用途 |
|---|---|
| `ws_probe.py` | 测试两种压缩订阅：cbor-raw vs 无压缩 |
| `verify_cbor.py` | 订阅 + CBOR 解码 + 字段结构核对 |
| `patch_subscribe.py` | patch 1 应用脚本 |
| `patch_outgoing.py` | patch 2 应用脚本 |
| `patch_cbor_conv.py` | patch 3 应用脚本 |

---

## 9. 关联与上下文

- **双 rosbridge 设计**（`a63463d docs: 设计 D360 双 rosbridge 分工`）：9090 在 core、19090 在 scout-nav，两者用不同节点名（`/rosbridge_websocket` 与 `/scout_nav_rosbridge`），共享同一 ROS Master
- **本次 patch 只针对 9090**（core 容器）；19090（scout-nav）的 rosbridge 是另一份代码，**未动**
- **没有动任何业务代码**（APP / d360_nav2D / SLAMIBOT_D360_Framework）
- 也没有动 nginx / FastAPI / ROS topic / 数据库 / 容器编排

---

## 10. 接手 checklist

接手人在动手前请确认：

- [ ] 通读本文件 §0-§4
- [ ] 跑 §5 "推荐诊断步骤" 三条命令，收集证据
- [ ] 根据证据判定根因（§5 的 5 个假设）
- [ ] 决定：是补 patch（再动 9090 rosbridge）、改 APP、还是别的
- [ ] 如补 patch：先 `cp /root/.ros/patches_20260819/*.orig` 备份到新目录，再改
- [ ] 任何修改前 `docker exec core bash -lc "md5sum <file>"` 记录当前值
- [ ] 修改后按 §7 流程重启 9090 rosbridge
- [ ] 修改后按 §6 把 patch 落进 Dockerfile / 启动脚本（**核心要求**）
- [ ] 在 `.ai-workspace/tasks/current.md` 登记任务条目（status + 引用本 known-issue）
- [ ] 在 `.ai-workspace/known-issues/` 新增 `app-map-cbor-rosbridge-fix-NN.md` 记录新进展
- [ ] 更新本文件 §4.5 与 §5


## 11. 2026-08-20 复核：当前阻塞是地图发布生命周期，不是 APP CBOR

- 当前运行镜像在调查开始时为 `scout-nav:initial-map-cloud-20260819`，不是旧记录中的 `scout-nav:dual-rosbridge-20260819`。
- `core` 的三处 live patch 仍存在，APP 连接 9090 后服务端记录了 `Subscribed to /map`。
- idle 状态下 `/map` 类型可见但没有 Publisher；`/plane_OccMap` 不存在。
- 调用导航模式接口后，`/map_server` 发布 `/map`，地图为 `1515x852`、分辨率约 `0.05`，同时默认点云 `/global_cloud_navigation` 保持发布。
- 2026-08-20 部署后再次使用 `tmp/verify_cbor.py` 验证 9090：收到 1,313,222 字节二进制首帧，顶层 `op/topic/msg`，`msg.data` 长度 1,290,780。
- WEB Topic 配置本来就是 `/map`；仅 `Map2DCanvas.tsx` 和 `PointsPage.tsx` 的用户提示仍写 `/plane_OccMap`。两处已改为 `/map` 并部署到 `scout-nav:map2d-topic-copy-20260820`。
- 当前结论：服务端 `/map` 与 APP CBOR 协议链路已恢复。APP UI 是否显示仍需用户真机复核；若失败，应采集当次 APP 日志，而不是继续猜测修改解析器。
- 尚未决策：点位管理是否必须在 idle 状态显示地图。若必须，应单独设计静态 `map_server` 生命周期及与 navigation 的互斥，禁止同时启动两个 `/map_server`。
- 回滚容器：`scout-nav-before-map2d-20260820-0958`；未删除旧容器和旧镜像。


## 12. 2026-08-20 用户验收与收尾

- 用户确认 WEB 与 APP 均已显示 2D 栅格地图，本问题状态改为 `RESOLVED_WITH_REMAINING_PERSISTENCE_RISK`。
- 源码已推送到 Gitee `origin/codex/fix-initial-map-cloud`，关键提交为 `e2e71bc`、`3244e75`、`6912fde`。
- 当前运行镜像仅保留 `scout-nav:map2d-topic-copy-20260820`；历史 scout-nav 容器和旧镜像标签已按用户授权精确删除，未执行 prune。
- 清理后再次验证 `/map`、WEB 活跃 bundle 和 9090 `cbor-raw` 首帧均 PASS。
- 未关闭的独立风险：core rosbridge 三处 CBOR patch 仍未持久化到 core 镜像源码。

## 2026-08-20 重启后复核

- Jetson 于 2026-08-20 重启后，`core` 容器仍运行，基础镜像为 `registry.cn-shanghai.aliyuncs.com/slamibot/slamibot_d360_firmware:latest`，镜像 ID `sha256:71ff42d71284ec2d08066c6d6824097e4610f7d5c1f9055db4a208a9d34d919f`。
- `docker diff core` 显示以下 rosbridge 文件仍为容器层修改：`subscribe.py`、`outgoing_message.py`、`cbor_conversion.py` 及对应 pyc。
- 容器内 `subscribe.py` 仍有 `if compression == "cbor-raw" and not msg_type:`；`outgoing_message.py` 仍有 2026-08-19 live patch 注释。
- 容器内文件 SHA256 与从基础镜像临时容器读取的 SHA256 不同，证明修复没有固化到基础镜像。
- 结论：本次重启只是复用了原 `core` 容器的可写层，因此 live patch 暂时保留；若删除/重建 core 容器或从基础镜像新建，修复仍会丢失。
