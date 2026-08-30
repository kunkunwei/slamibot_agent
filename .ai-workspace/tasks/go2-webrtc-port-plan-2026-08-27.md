# 移植方案：scout-nav 2D 导航容器接入 WebRTC 控制宇树 GO2（2026-08-27）

> **已升级为完整交接文档**：`procedures/go2-webrtc-control-handoff-2026-08-27.md`（自包含，以该文档为准）。本文件为方案初稿。
> 任务登记：`tasks/current.md` → `TASK-2026-08-27-003`。
> 状态：PLAN（只读分析，未改任何代码）
> 结论先行：**当前 scout-nav 容器只有 GO2 状态机 + 网络探测，无 WebRTC 驱动**。可参考外协 3D 导航（movebase3d_web）的完整 WebRTC 实现移植。

## 一、现状（已确认，代码证据）

### scout-nav 容器（scout-nav-timefix-20260827，镜像 scout-nav:jetson0826-src-timefix-20260827）
- `base_mode.py:1` 状态机 `NONE / SCOUT (managed roslaunch) / GO2 (driver not configured)`
- `base_mode.py:616-630` `_switch_to_go2_locked()`：停 Scout → `mode=GO2` → `ready=False` → `reason="GO2_DRIVER_NOT_CONFIGURED"`，返回 `success=True "已选择 GO2, 但驱动未配置"`
- `base_mode.py:331-361` `_probe_go2()`：仅 `ip route get` + `ping` + `ip neigh`，判定网络可达（`candidateDetected/networkReachable`），`identityVerified=False, ready=False`。注释（56-57）明说 `no WebRTC Init()`
- 容器内**无** `unitree_webrtc_connect` / `go2_sdk_manager` / `WebRTCSportClient` / `unitree_sdk2py`（pip list 无 webrtc/unitree/aiortc/websockets）
- 容器网络 = host；`192.168.123.161 dev eth2 src 192.168.123.55` 路由已存在（GO2 USB 网口）
- Python 3.8.10，site-packages 含 `/usr/local/lib/python3.8/dist-packages`
- 已有 teleop 链路：`/cmd_vel_web`（APP 摇杆 25Hz）→ teleop.py（enable/disable watchdog）→ `/cmd_vel`

### 外协 3D 导航参考实现（movebase3d_web，nav3d_d360:1.0 容器）
- `sdk/go2_sdk_manager.py`（220 行）：`initialize()` 里 WebRTC 分支启用 `WebRTCSportClient`（运动控制），DDS `SportClient` 分支被注释；视频 `VideoClient`（unitree_sdk2py DDS）失败仅告警。`cleanup()` 调 WebRTC `cleanup()`
- `sdk/webrtc_sport_client.py`（144 行）：`WebRTCSportClient` 模仿 unitree_sdk2py `SportClient` 接口，`AsyncBridge`（asyncio 线程）+ `UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=192.168.123.161)`；Init = connect → `_ensure_normal_mode`（MOTION_SWITCHER api 1001/1002 切 normal）→ FreeWalk。API：`Move/StopMove/StandUp/StandDown/Sit/Hello/Stretch/FreeWalk/BalanceStand/SwitchGait/cleanup`
- `go2_control.py`：订阅 `/cmd_vel_cmu|web|ang`（Twist）→ `sport_client.Move(vx,vy,wz)`；`VEL_DEADBAND=0.03 / YAW_DEADBAND=0.05`；静止时发一次 `StopMove`（normal 固件持续 Move(0,0,0) 会原地踏步）；`/go2_action_command` → StandDown/Sit/Hello/Stretch/StandUp；`SwitchGait` 支持 freewalk/economic
- `action/action_manager/base_manager.py:144-145`：sports 类动作依赖 `get_go2_sdk_manager().get_sport_client()`

### 依赖（宿主机 /home/jetson 已具备，python3.8 与容器一致）
- `unitree-webrtc-connect 2.1.2`：`/home/jetson/.local/lib/python3.8/site-packages/unitree_webrtc_connect`
- `unitree-sdk2py 1.0.1`：源码 `/home/jetson/unitree_sdk2_python`（视频 DDS 用，可降级）
- aiortc 1.9.0 + aioice 0.9.0 + av 12.3.0 + pyee + cryptography + google_crc32c（编译扩展，宿主机 3.8 与容器 3.8 二进制兼容）
- websockets 13.1 / websocket-client 1.8.0 / simple-websocket 1.1.0

## 二、目标

让 `switch(mode=go2)` 真正接通 WebRTC：
1. base_mode 初始化 Go2SdkManager（WebRTC）→ 连接 GO2 → `ready=true` + `armed`
2. GO2 运动控制接入现有 `/cmd_vel_web` 摇杆链路（或 `/cmd_vel`），base_mode 严格 gate
3. scout 模式完全不受影响（互斥由 base_mode switch 保证）

## 三、改动清单（实施时执行，本次未动）

### A. 依赖部署（scout-nav 容器）
把宿主机已验证的 WebRTC 依赖部署进容器（Python 3.8.10 与宿主机一致，直接拷贝 site-packages 或离线 pip）：
- `unitree_webrtc_connect`、`aiortc`、`aioice`、`av`(+av.libs)、`pyee`、`cryptography`、`google_crc32c`、`websockets`、`websocket-client`、`simple-websocket`
- `unitree-sdk2py`（源码拷贝或 editable install；若不做视频可只装 `unitree_sdk2py.core.channel` 所需部分）
- 安装到容器 `/usr/local/lib/python3.8/dist-packages/`
- **持久化方式（二选一，需用户定）**：
  - (a) 依赖放宿主机 `Scout_mini_navigation/vendor/`，改 `Dockerfile`（`COPY install/` 处追加 `COPY vendor/...`）rebuild 镜像 —— 推荐，可 git 管理
  - (b) docker cp 进容器后 `docker commit` 生成新镜像（不进 git，回滚靠镜像标签）
- 容器启动注入 env：`UNITREE_ROBOT_IP=192.168.123.161`、`GO2_NETWORK_INTERFACE=eth2`

### B. 代码移植（容器内 fastapi_service）
1. **新增 `fastapi_service/go2/` 子包**：
   - `go2_sdk_manager.py`（移植外协版，去掉 robot_web_controller/common 耦合，日志改 fastapi 的 LOGGER）
   - `webrtc_sport_client.py`（移植，依赖如上）
   - `go2_control.py`（可选）：cmd_vel → Move 桥接（订阅 `/cmd_vel_web` 或 `/cmd_vel`）
2. **`base_mode.py` 改动**：
   - `_switch_to_go2_locked()`：`Go2SdkManager().initialize()` → 成功则 `_ready=True`、`_reason` 清空、连接 Go2SdkManager 到管理器实例；失败回滚 `GO2_DRIVER_NOT_CONFIGURED`/记录具体原因
   - `shutdown()`：GO2 分支调 `sdk_manager.cleanup()` + teleop disable
   - `status` 增加 GO2 连接字段（`webrtcConnected` / `armed`）
   - `_probe_go2()` 保持网络探测；可加"WebRTC connect 成功即 identityVerified=True"（二期）
3. **运动 gate**：GO2 就绪 + teleop enabled 时才执行 Move；静止发 StopMove；任何异常 StopMove 兜底
4. **action.py**（可选二期）：`stand_up/stand_down/sit/hello/stretch` 在 go2 模式下路由到 sport_client

## 四、风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| av/cryptography 二进制兼容 | aiortc 1.9.0 + av 12.3.0 是编译扩展 | 宿主机与容器均为 python3.8，实测 import 后再固化镜像 |
| GO2 固件/协议匹配 | unitree_webrtc_connect 2.1.2 的 api_id 与目标 GO2 固件版本是否一致 | 外协同型号已验证；实机联调确认 MOTION_SWITCHER/SPORT_CMD 返回码 |
| 运动安全 | armed + Move 属运动控制 | base_mode 严格 gate + watchdog + 异常 StopMove；与 scout 互斥 |
| 持久化 | pip 包不进 git | 走 vendor/ + Dockerfile 或 docker commit（用户定） |
| 回归 scout | base_mode 改动波及 scout 分支 | 保持 SCOUT 分支逻辑不变；回归测试 scout switch |

## 五、验证步骤

1. 容器内 `import unitree_webrtc_connect / aiortc / websockets` 全通过
2. 无 GO2 实机：`switch(mode=go2)` → status 正确回 `GO2_DRIVER_NOT_CONFIGURED` 或明确连接失败原因（静态验证状态机不崩）
3. 有 GO2 实机（需授权 DEPLOY）：`switch(mode=go2)` → `webrtcConnected=true, armed=true`；APP 摇杆 → GO2 运动；静止 → StopMove
4. 回归：`switch(mode=scout)` → scout 底盘正常

## 六、工作量 / 阶段

- **阶段1（静态）**：依赖部署 + sdk 层移植 + base_mode 接通 + import/状态机验证（可无 GO2）
- **阶段2（实机）**：GO2 联调运动控制 + 摇杆链路 + 安全 gate 实测（需 GO2 + 用户授权 DEPLOY）

## 七、待用户确认

1. 持久化方式：(a) vendor/ + Dockerfile rebuild（推荐，进 git）还是 (b) docker commit
2. 运动控制接 `/cmd_vel_web`（复用 APP 摇杆，推荐）还是独立 `/cmd_vel` 桥接
3. 是否含视频（VideoClient）——建议一期只做运动控制，视频二期
4. 是否现在按阶段1实施
