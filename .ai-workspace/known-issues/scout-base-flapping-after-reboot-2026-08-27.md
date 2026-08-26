# Scout 底盘激活重启后变 NONE：驱动横跳（flapping）诊断

- 日期：2026-08-27
- 状态：resolved（用户物理重启小车后恢复）
- 相关：`scout-nav` 容器（ROS1 Noetic）、base_mode（底盘模式 API）、`nav-healthcheck.sh`
- 技术栈：ROS1（CURRENT）

## 现象
- D360 计算单元重启 + OAK 相机过热（100°C→降温至 78°C）之后，APP 显示「底盘激活 NONE」。
- `/api/base_mode/status`：`activeBase=NONE`、`reason=SCOUT_NODE_MISSING`、`managedScoutRunning=false`，但 `bases.SCOUT.detected=true`（网络上能探测到底盘）。
- 该状态持续不恢复，除非物理重启小车（底盘整机）。

## 排查结论（关键证据）
1. **base_mode 对齐热修并未丢**：容器 `base_mode.py` 1028 行（`_probe_scout`×7、`policy`×16、`activeBase`×3），API 返回新契约字段完整。容器可写层在整机重启后保留（`install` 目录非 bind mount，但容器对象未重建）。
2. **自动重连在跑**：`nav-healthcheck.sh:71-81` 底盘节点未注册时调 `switch?mode=scout` 自愈，日志显示反复执行。
3. **驱动在横跳**：`/tmp/scout_base_mode.log` 约 20 轮 `started roslaunch → process[scout_base_node] started → killing on exit`（约每 30s 一轮）。`killing on exit` 是 base_mode 管理器 `_terminate_record` 发的 SIGINT。
4. **CAN 物理层正常**：`can0 UP / ERROR-ACTIVE / 500kbps`；宿主机与容器 `candump can0` 均能看到底盘帧（ID 0x221/0x241/0x251-0x254/0x311/0x261），RX 约 400 pkt/s。
5. **驱动注册却无输出**：`/scout_base_node` 注册、`/scout_status` 挂发布者，但 `rostopic echo/hz` 窗口内**零消息**（`no new messages`），/odom 同样无数据。驱动仅打印 `Detected protocol: AGX_V2`、`Start listening to port: can0`。
6. **验证失败即杀**：`_switch_to_scout_locked()` → `_wait_for_scout_status()`（`base_mode.py:866-887`）要求 8s 内 `control_mode=1 && fault_code=0`，不满足即 `_terminate_record` → mode=NONE。具体失败是 `SCOUT_STATUS_TIMEOUT` 还是 `SCOUT_STATUS_UNHEALTHY` 未捕获到（横跳窗口太短，抓值前用户已重启）。
7. 偶见 `Reason given for shutdown: new node registered with same name` —— 同名 `/scout_base_node` 竞争被 master 挤掉。

## 根因判断（推测，未逐条证实）
- 底盘控制器（STM32/主控）在过热 + 计算单元重启后处于**半初始化/异常状态**：持续发 CAN 帧，但 `scout_base_node` 驱动解析不出有效的 AGX_V2 状态序列 → 发不出 `/scout_status` → 8s 验证失败 → 驱动被终止 → healthcheck 每 60s 再拉起 → 无限横跳。
- 与 2026-08-26 的「STM32 USB Hub 掉线需物理重启」同类，属**硬件级状态异常**，软件无法自愈。
- 不是 base_mode 代码 bug：自动重连按设计在反复触发，卡点在驱动永远达不到 ready。

## 解决 / 规避
- **用户物理重启小车（底盘整机断电重启）** → 控制器回到干净状态 → `activeBase=SCOUT`、`ready=True`、`/scout_status` 50Hz、`/odom` 50Hz。✓
- 后续遇到同样「驱动注册但 /scout_status 零消息」且 CAN 有流量 → 优先尝试底盘整机重启，不必改代码。

## 遗留
- 若复现，建议先抓一帧真实 `/scout_status` 值（`control_mode`/`fault_code`）确认是超时还是 unhealthy，再判断是否需调验证策略。
- OAK 相机 100°C 过热是本次的前置诱因，需观察是否复发（可能伴随散热/供电问题）。
