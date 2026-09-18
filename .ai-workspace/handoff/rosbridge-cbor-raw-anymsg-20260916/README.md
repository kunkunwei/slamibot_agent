# D360 点云不显示（结论已更正）：**固件里的 rosbridge 对 `cbor-raw` 订阅强制通配类型**

- 日期：2026-09-16（当日 20:20 更正结论）
- 现场设备：715 = `192.168.31.164`（core 容器 rosbridge 端口 9090）
- 对照设备：701 = `192.168.31.135`（同镜像族，长期正常）
- 交付物：`repro_ws_probe.py`（复现/验收）、`verify_on_device.sh`（设备侧取证）、`evidence/`（原始日志与补丁差异）

---

## 一、结论（已更正）

**根因在设备端固件，不在 APP。** `d360_nav2d` / 固件镜像里那份 rosbridge 的
`rosbridge_library/capabilities/subscribe.py` 第 120 行是：

```python
if compression == "cbor-raw":                 # ← stock（ACR 镜像、715 现状）
    msg_type = "__AnyMsg"
```

**只要客户端用 `cbor-raw` 订阅，就把消息类型无条件改成 `__AnyMsg`（通配）**，客户端自己带没带 `type` 都不看。
于是：该话题被登记成通配 → WEB 的带类型订阅被拒 / cbor 编码抛 `AttributeError: 'AnyMsg' object has no attribute '_slot_types'`
→ **APP 与 WEB 同时看不到点云**。APP 的订阅姿势没有问题。

701 之所以一直正常，是因为它的 core 容器里这份文件被人手改过：

```python
if compression == "cbor-raw" and not msg_type:  # ← 701 现状（只有客户端确实没带 type 时才用 AnyMsg）
    msg_type = "__AnyMsg"
```

**这是一处只在 701 上手工存在、任何镜像里都没有的补丁**（同批还有 `cbor_conversion.py`、`outgoing_message.py` 两个，共 3 个文件，
见 `evidence/subscribe.py.diff` 与 `artifacts/firmware-rosbridge-cbor-patch-20260819/`）。

### 行为对照（可复现）

| APP（cbor-raw 订阅者）是否在线 | 715 现状（stock） | 701（已打补丁） |
|---|---|---|
| 在线 | 话题被锁成通配：WEB 被拒 / 静默失败 → **都看不到** | 正常，类型正确登记 → **都能看到** |
| 离线 | 注册被清理，WEB 恢复正常（2026-09-16 20:14 实测：cbor 收到 20 条 / 13 MB → PASS） | 正常 |

> **APP 不需要改代码。** 之前那份"APP 订阅不带 type"的判断是错的，已作废，请不要转给 APP 开发。
> 唯一建议 APP 侧自查的是日志里另一条 `cbor-raw is not a valid type string`（19:00、19:01，来源未定）——
> 若确认是自己的报文拼装问题就顺手修掉；与本次点云问题无关。

---

## 二、证据（逐字，含时间戳）

### 2.1 补丁差异（决定性）

`evidence/subscribe.py.diff` —— 701 与 715 的 `capabilities/subscribe.py` 全文差异只有这一处：

```diff
@@ -117,7 +117,7 @@
-        if compression == "cbor-raw":
+        if compression == "cbor-raw" and not msg_type:
             msg_type = "__AnyMsg"
```

`rosbridge_library` + `rosbridge_server` 两棵包逐文件对指纹（56 个 .py）后，**只有 3 个文件不同**：
`capabilities/subscribe.py`、`internal/cbor_conversion.py`、`internal/outgoing_message.py` —— 全部在 701 侧是改过的，715 侧是原版。
（提取件：`artifacts/firmware-rosbridge-cbor-patch-20260819/{stock,patched,diffs}/`）

### 2.2 现象：APP 的 cbor-raw 订阅一上线，话题立刻变通配

`evidence/app-logcat-subscribe.log`（APP 自己的日志）：

```
09-16 20:01:25.389 I/RosbridgeSession(24610): Native control session connected: ws://192.168.31.164:9090
09-16 20:01:27.781 I/NativePointCloud(24610):   Point-cloud subscribe (cbor-raw, throttle=0ms, queue=1): /global_cloud_navigation
09-16 20:02:01.177 W/NativePointCloud(24610):   Native point-cloud connection failed: Socket closed
```

`evidence/rosbridge-all-instances.log`（设备侧同一时刻）：

```
20:01:27,498: [Client 2] Subscribed to /global_cloud_navigation        ← APP（cbor-raw）
20:01:27,504: [Client 3] Subscribed to /map
20:02:42,273: [ERROR] [Client 5] [id: probe] subscribe:
              Tried to register topic /global_cloud_navigation with type sensor_msgs/PointCloud2
              but it is already established with type *                ← 带类型订阅被拒
```

### 2.3 现场实测复现（发布侧健康）

`evidence/715-anymsg-live.log`：2026-09-16 20:11~20:12，发布侧 `/global_cloud_navigation` 10.000 Hz、
`/livox/lidar` 9.999 Hz、`/Odometry` 10.063 Hz，用本包脚本复现：

```
20:11:18,296: [ERROR] [Client 7] [id: repro-probe] ... already established with type *
20:11:33,535: [INFO]  [Client 8] Subscribed to /global_cloud_navigation     ← APP 再次注册
20:12:05,029: [ERROR] [Client 9] [id: repro-probe] ... already established with type *
```

### 2.4 APP 离线后立刻恢复

同一脚本、同一参数，APP 不在线时（20:14）：`cbor` 收到 **20 条 / 13 MB → PASS**。
→ 故障与"谁在订阅"完全对应，与 APP 是否带 type 无关。

### 2.5 对照设备 701

```
# 701 rosbridge 日志
# already-established-with-type 次数: 0
# is-not-a-valid-type-string 次数: 0
# AnyMsg 次数: 0
```

带类型探针订阅 701：`cbor` 37 条/12s、`cbor-raw` 正常。

---

## 三、修法（设备端/固件）

1. **把第 3 个补丁并入固件镜像**（连同已在 701 生效的另外两个）：
   `capabilities/subscribe.py` 改为 `if compression == "cbor-raw" and not msg_type:`
   然后构建并推送新 tag（并把 `slamibot_d360_firmware:latest` 指过去），新装机自然带修复。
2. **715 现场**：把这份 subscribe.py 也热补进 core 容器（另两个补丁本次已写入），重启 core 即可生效；
   在此之前只要 APP 在线，WEB 就看不了点云。
3. APP：**无需改动**。

---

## 四、怎么复现 / 怎么验收

### 复现（任何一台同网段的 PC）

```bash
pip install websocket-client

# 1) 带类型（WEB 的方式）——当前会被拒绝
python repro_ws_probe.py --url ws://192.168.31.164:9090 --compression cbor

# 2) 不带类型（APP 当前的做法）——把话题毒化，别人全废
python repro_ws_probe.py --url ws://192.168.31.164:9090 --compression cbor --no-type

# 3) 把压缩方式填进 type（现场日志那种）——invalid type string
python repro_ws_probe.py --url ws://192.168.31.164:9090 --compression cbor-raw --type-as-compression
```

现场已观测的对照结果：

| 场景 | APP 在场 | 结果 |
|---|---|---|
| `--compression cbor`（WEB） | 是 | 0 条，且被拒（`already established with type *`） |
| `--compression cbor-raw`（APP） | 否 | 26~33 条 / ~650KB each |
| 701 同参数 `cbor` | — | 37 条 / 12s |

### 设备侧取证（只读）

```bash
scp verify_on_device.sh jetson@<设备>:/tmp/ && ssh jetson@<设备> 'bash /tmp/verify_on_device.sh'
```

### 验收标准（APP 改完后，APP 与探针同时在线）

1. rosbridge 日志里 `already established with type *` / `AnyMsg` / `is not a valid type string` **全部为 0**；
2. 探针 `--compression cbor`（WEB 等价）**能持续收到点云**；
3. APP 自身能渲染 3D 点云，WEB 端同时也能看到。

---

## 五、文件清单

| 文件 | 说明 |
|---|---|
| `repro_ws_probe.py` | 复现/验收脚本，带 PASS/FAIL 判读；`--no-type`、`--type-as-compression` 可分别复现两种错法 |
| `verify_on_device.sh` | 设备侧只读取证：连接、订阅序列、三类错误计数、发布侧频率 |
| `evidence/app-logcat-subscribe.log` | APP logcat 原文（`NativePointCloud` / `OccupancyGridClient` / `RosbridgeSession`） |
| `evidence/rosbridge-all-instances.log` | 715 core 容器里所有 rosbridge 实例的关键行（含 19:01~20:02 的全部拒绝记录） |
| `evidence/rosbridge-715-keys.log` | 715 当前实例的关键行（含 `[id: probe]` 被拒） |
| `evidence/715-current-counts.txt` | 715 当前计数（`already-established=1`，`AnyMsg=0`） |
| `evidence/701-control-counts.txt` | 701 对照计数（三项全 0） |
| `evidence/715-anymsg-live.log` | **本次现场实测**：带类型订阅被拒 + 无类型客户端成功注册（20:11~20:12） |
| `../known-issues/rosbridge-untyped-subscribe-poisons-topic-2026-09-16.md` | 完整背景与本次在 715 上做过的改动（含回滚点） |
