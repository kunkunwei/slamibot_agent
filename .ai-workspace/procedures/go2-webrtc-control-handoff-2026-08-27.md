# 交接文档：scout-nav 2D 导航容器接入 WebRTC 控制宇树 GO2（2026-08-27）

> 交接给：后续 AI 会话 / 开发人员。本文档自包含，标注的事实均已核实（CONFIRMED），
> 引用源码用 `路径:行号`。任务登记：`tasks/current.md` → `TASK-2026-08-27-003`。
> 方案初稿：`tasks/go2-webrtc-port-plan-2026-08-27.md`（本文档为增强版，以本文档为准）。
> 本会话**未改动任何代码/容器/镜像**，全部为只读侦查结论。

---

## 1. 背景与目标

用户在旧容器实现过「2D 导航 3D 点云里轨迹+箭头实时移动」（已确认新容器等价实现，见 `known-issues/api-bridge-backend-completion-scout-nav-2026-08-27.md`）。
现在需求：**让当前 2D 导航容器 `scout-nav-timefix-20260827` 能通过 WebRTC 控制宇树 GO2**（把 GO2 作为可切换底盘之一）。

现状：容器 `base_mode.py` 状态机**已支持** `switch(mode=scout|go2)`，但 GO2 分支只是「网络探测 + 标记驱动未配置」，**没有 WebRTC 驱动**。

## 2. 已确认事实（全部证据）

### 2.1 scout-nav 容器现状（CONFIRMED）
- 容器 `scout-nav-timefix-20260827`（镜像 `scout-nav:jetson0826-src-timefix-20260827`），运行中。
- 容器内 FastAPI 双路径：`install = /Scout_mini_navigation/install/lib/python3/dist-packages/fastapi_service/`（运行时加载）；宿主机 git = `/home/jetson/Scout_mini_navigation/`（src + install，分支 `jetson/0826` → `github.com:kunkunwei/Scout_mini_navigation.git`）。**install 版与宿主机 src 版 base_mode.py md5 一致**。
- `base_mode.py`（1028 行状态机，本会话之前补全）：
  - `:1` docstring `NONE / SCOUT (managed roslaunch) / GO2 (driver not configured)`
  - `:47-48` `MODE_GO2 = "GO2"`，`VALID_MODES = (NONE, SCOUT, GO2)`
  - `:56-57` 注释：`no WebRTC Init(), mode switch, enable service or motion command is invoked by this module`
  - `:61-62` `GO2_ROBOT_IP = env UNITREE_ROBOT_IP, 默认 192.168.123.161`；`GO2_NETWORK_INTERFACE = env GO2_NETWORK_INTERFACE, 默认 eth2`
  - `:331-361` `_probe_go2()`：`ip route get` + `ping` + `ip neigh` → `candidateDetected/networkReachable`；`identityVerified=False, ready=False`，reason=`GO2_ROUTE_UNAVAILABLE` / `GO2_NETWORK_UNREACHABLE` / `GO2_IDENTITY_UNVERIFIED`
  - `:456-459`、`:616-630` `_switch_to_go2_locked()`：停 Scout → `mode=GO2` → `ready=False` → `reason="GO2_DRIVER_NOT_CONFIGURED"` → 返回 `success=True "已选择 GO2, 但驱动未配置"`
- 容器内**无** `unitree_webrtc_connect` / `unitree_sdk2py` / `go2_sdk_manager` / `WebRTCSportClient`（find + grep + pip list 均空）。
- 容器 `NetworkMode=host`；`ip route get 192.168.123.161` → `dev eth2 src 192.168.123.55`（GO2 USB 网口路由已通）。容器内**无 ping 命令**（超最小镜像）。
- 容器 Python **3.8.10**（`/usr/bin/python3`），site-packages：`/usr/local/lib/python3.8/dist-packages`、`/usr/lib/python3/dist-packages`、`/usr/lib/python3.8/dist-packages`；pip 20.0.2。
- 已有 teleop 链路：`/cmd_vel_web`（APP 摇杆 25Hz）→ `teleop.py`（enable/disable watchdog，输出 `/cmd_vel`）。`teleop.py:52` `TELEOP_INPUT_TOPIC = "/cmd_vel_web"`。
- `action.py` 已有底盘动作占位（stand_up/stand_down/sit/hello/stretch/photo），`execute` 当前返回「动作暂未实现」。
- Dockerfile：`/home/jetson/Scout_mini_navigation/Dockerfile`，`:96` `COPY install/`（镜像构建用宿主机 install/）。

### 2.2 外协参考实现（CONFIRMED，完整 WebRTC 链路，在 3D 外协导航 movebase3d_web）
源码根：`/home/jetson/docker_ws_backup/src/robot_web_controller/scripts/robot/unitree_go2/`
- `sdk/go2_sdk_manager.py`（220 行）：
  - `_UNITREE_SDK2 = "/home/jetson/unitree_sdk2_python"`（或 env `UNITREE_SDK2_PYTHON_PATH`），用于 `import unitree_sdk2py`
  - `initialize()` 启用 WebRTC 分支：`from unitree_sdk2py.core.channel import ChannelFactoryInitialize`、`from unitree_sdk2py.go2.video.video_client import VideoClient`、`from .webrtc_sport_client import WebRTCSportClient`；运动控制 = `WebRTCSportClient()`（**不 Init DDS SportClient**，DDS 分支被注释）；视频 `VideoClient` 失败仅 `logwarn` 不阻断
  - `cleanup()` 调 `sport_client.cleanup()`
  - 导出 `create_go2_sdk_manager()`
- `sdk/webrtc_sport_client.py`（144 行）：
  - 依赖 `unitree_webrtc_connect`：`from unitree_webrtc_connect.webrtc_driver import (UnitreeWebRTCConnection, WebRTCConnectionMethod)`、`from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD`
  - `ROBOT_IP = env UNITREE_ROBOT_IP 默认 192.168.123.161`
  - `WebRTCSportClient`：`AsyncBridge`（asyncio 线程）+ `UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip)`；`Init()` = connect → `_ensure_normal_mode()`（MOTION_SWITCHER api 1001 查 / 1002 切 normal）→ FreeWalk
  - API 面（模仿 unitree_sdk2py SportClient）：`Move(vx,vy,vyaw)` / `StopMove` / `StandUp`（内部 +BalanceStand） / `StandDown` / `Sit` / `Hello` / `Stretch` / `FreeWalk` / `BalanceStand` / `SwitchGait('freewalk'|'economic')` / `cleanup`；`SetTimeout` 空实现
- `go2_control.py`：订阅 `/cmd_vel_cmu`、`/cmd_vel_web`、`/cmd_vel_ang`（Twist）→ `sport_client.Move(vx,vy,wz)`；`VEL_DEADBAND=0.03 / YAW_DEADBAND=0.05`；**静止时发一次 StopMove**（normal 固件持续 Move(0,0,0) 会原地踏步）；`/go2_action_command`（String）→ StandDown/Sit/Hello/Stretch/StandUp；`/go2_stop_action`（Bool）→ StopMove
- `scripts/common.py:124-128, 282-287`：`get_go2_sdk_manager()` 工厂（Go2SdkManager 单例）
- `action/action_manager/base_manager.py:144-145`：sports 类动作取 `get_go2_sdk_manager().get_sport_client()`

### 2.3 依赖（宿主机已装齐，python3.8 与容器一致 = 二进制兼容）
位置 `/home/jetson/.local/lib/python3.8/site-packages/`：
- `unitree_webrtc_connect`（2.1.2）—— 核心 WebRTC 客户端
- `unitree-sdk2py` 1.0.1（源码 `/home/jetson/unitree_sdk2_python`，editable 安装）—— 视频 DDS + ChannelFactoryInitialize
- `aiortc` 1.9.0、`aioice` 0.9.0、`av` 12.3.0（+ `av.libs`，编译扩展）、`pyee`、`cryptography` 47.0.0、`google_crc32c`
- `websockets` 13.1、`websocket-client` 1.8.0、`simple-websocket` 1.1.0
- 外协镜像 `nav3d_d360:1.0` 内已装 `aiortc 1.9.0 / websockets 13.1 / websocket-client 1.8.0 / unitree_sdk2py→/workspace/unitree_sdk2_python`；但该镜像 **find 未发现 `unitree_webrtc_connect`**（外协容器如何 import 成功待接手自查——可能走宿主机 `.local` 或镜像内另有 python 环境）。

### 2.4 其他
- 端口 `0.0.0.0:5001` 在 Jetson 上 LISTEN（进程归属未确认，可能属 firmware 容器，与本任务无直接关系）。
- GO2 在线探测目标：`192.168.123.161`（`UNITREE_ROBOT_IP`）、接口 `eth2`（`GO2_NETWORK_INTERFACE`）。

## 3. 实施方案

### A. 依赖部署进 scout-nav 容器（Python 3.8.10 与宿主机一致）
1. 拷贝宿主机已验证依赖到容器 `/usr/local/lib/python3.8/dist-packages/`：`unitree_webrtc_connect` + `aiortc` + `aioice` + `av`(+`av.libs`) + `pyee` + `cryptography` + `google_crc32c` + `websockets` + `websocket-client` + `simple-websocket`；`unitree_sdk2py`（源码或 editable）。
2. **持久化方式（待用户定）**：
   - (a) 依赖放宿主机 `Scout_mini_navigation/vendor/`，改 `Dockerfile`（追加 `COPY vendor/...`）rebuild 镜像 —— 推荐，可 git 管理；
   - (b) `docker cp` 进容器后 `docker commit` 生成新镜像（不进 git，回滚靠镜像标签）。
3. 容器 env 注入：`UNITREE_ROBOT_IP=192.168.123.161`、`GO2_NETWORK_INTERFACE=eth2`。

### B. 代码移植（容器内 fastapi_service，两处同步：install + 宿主机 src）
1. 新增 `fastapi_service/go2/` 子包：
   - `go2_sdk_manager.py`（移植外协版，去掉 `robot_web_controller`/`common` 耦合，日志改 fastapi `LOGGER`）
   - `webrtc_sport_client.py`（移植，依赖如上）
2. `base_mode.py` 改动：
   - `_switch_to_go2_locked()`：`Go2SdkManager().initialize()` 成功 → `_ready=True`、`_reason` 清空、实例挂到管理器；失败回滚并记录具体原因
   - `shutdown()`：GO2 分支调 `sdk_manager.cleanup()` + teleop disable
   - `status` 增加 GO2 连接字段（`webrtcConnected` / `armed`）
   - `_probe_go2()` 保留网络探测；可选加「WebRTC connect 成功即 `identityVerified=True`」
3. 运动 gate：仅 `GO2 就绪 + teleop enabled` 时执行 Move；静止发 StopMove；异常兜底 StopMove。
4. `action.py`（可选二期）：stand_up/stand_down/sit/hello/stretch 在 go2 模式下路由到 sport_client。

## 4. 关键路径 / 命令

```bash
# 容器（运行中）：scout-nav-timefix-20260827
C=scout-nav-timefix-20260827
docker exec $C bash -lc "python3 -c 'import unitree_webrtc_connect' "   # 移植后应通过

# 宿主机依赖源
ls /home/jetson/.local/lib/python3.8/site-packages/ | grep -E "unitree|aiortc|aioice|^av|websocket"

# 外协参考实现
#   /home/jetson/docker_ws_backup/src/robot_web_controller/scripts/robot/unitree_go2/sdk/go2_sdk_manager.py
#   .../sdk/webrtc_sport_client.py
#   .../go2_control.py

# 宿主机 git（持久化）：/home/jetson/Scout_mini_navigation/，分支 jetson/0826 → github.com:kunkunwei/Scout_mini_navigation.git
# 镜像构建：/home/jetson/Scout_mini_navigation/Dockerfile（:96 COPY install/）
```

## 5. 验证步骤

1. 容器内 `import unitree_webrtc_connect / aiortc / websockets` 全通过。
2. 无 GO2 实机静态验证：`switch(mode=go2)` → status 不崩，正确回 `GO2_DRIVER_NOT_CONFIGURED` 或明确连接失败原因。
3. 有 GO2 实机（需授权 DEPLOY）：`switch(mode=go2)` → `webrtcConnected=true, armed=true`；APP 摇杆（`/cmd_vel_web`）→ GO2 运动；静止 → StopMove。
4. 回归：`switch(mode=scout)` → scout 底盘正常；`/api/action/list` 正常。

## 6. 风险与边界（必须遵守）

- **零破坏**：默认只读。ROS1 是 CURRENT 稳定基线；**严禁** ROS1→ROS2 迁移、改动 rosbridge/前后端契约、清理地图/数据库、重写 Git 历史。
- 容器重启会丢容器内进程/依赖（非镜像层改动）→ 依赖必须走 vendor/Dockerfile 或 docker commit 持久化。
- `scout_base` 底盘驱动由 base_mode managed scout 管理；GO2 与 SCOUT 互斥（base_mode switch 已保证）。
- 运动控制（armed + Move）属安全关键：严格 gate + watchdog + 异常 StopMove；实机联调需现场物理急停条件 + 用户授权 DEPLOY。
- 宿主机 git（`/home/jetson/Scout_mini_navigation/`）有**大量用户未提交修改**，提交时只动任务 scope 文件，不得 `git add -A`。
- av/cryptography 为编译扩展：宿主机与容器同为 python3.8，但**实测 import 后再固化镜像**。
- GO2 固件 api_id 与 `unitree_webrtc_connect 2.1.2` 的匹配：外协同型号已验证；实机联调确认 `MOTION_SWITCHER`/`SPORT_CMD` 返回码。
- 外协容器内 `unitree_webrtc_connect` 未在镜像 find/pip 命中 —— 接手时先澄清外协实际加载路径，再决定拷贝方案（否则 import 可能失败）。

## 7. 待确认 / 授权点

1. 依赖持久化方式：(a) `vendor/` + Dockerfile rebuild（推荐）vs (b) `docker commit`。
2. GO2 运动控制链路：复用 `/cmd_vel_web` 摇杆（推荐，APP 不改）vs 独立 `/cmd_vel` → Move 桥（类外协 go2_control.py）。
3. 是否含视频 `VideoClient`（一期建议只做运动控制，视频二期）。
4. 是否现在实施阶段1（装依赖 + 移植 sdk + base_mode 接通，无实机静态验证）。
5. 实机联调需 GO2 + 用户授权 DEPLOY。
