# 底盘模式切换与 Scout 启停

> 状态：CONFIRMED（2026-08-20 实机验证）  
> 适用范围：当前 ROS1 Noetic `scout-nav` 容器与松灵 Scout mini 底盘。  
> 日常操作统一使用 FastAPI 模式接口；不要直接手动启动 `scout_base_node`，以免与受管进程冲突。

## 当前部署事实

- Jetson：`192.168.31.135`
- FastAPI：`http://192.168.31.135:5000`
- 当前容器：`scout-nav`
- 当前镜像：`scout-nav:base-mode-ready-20260820`
- 容器启动后的安全默认值：`mode=NONE`、`teleopEnabled=false`
- Scout CAN：`can0`，`500000 bit/s`
- Scout 健康条件：`control_mode=1` 且 `fault_code=0`
- GO2 当前只是安全占位模式，尚未配置驱动；不得把 ROS2 GO2 启动命令混入本 ROS1 操作手册。

## Windows PowerShell：日常模式命令

### 1. 查询当前底盘模式

```powershell
curl.exe -sS "http://192.168.31.135:5000/api/base_mode/status"
```

### 2. 启动并切换到 Scout 底盘

```powershell
curl.exe -sS -X POST "http://192.168.31.135:5000/api/base_mode/switch?mode=scout"
```

成功时重点检查返回值：

```text
mode=SCOUT
ready=true
teleopEnabled=false
managedScoutRunning=true
```

切换成功后摇杆仍保持禁用，必须由操作者明确启用。

### 3. 切回 NONE，停止受管 Scout 底盘节点

```powershell
curl.exe -sS -X POST "http://192.168.31.135:5000/api/base_mode/switch?mode=none"
```

`NONE` 会先禁用 teleop、发布零速并停止受管 Scout 节点，但不会关闭 `can0`。小车断电或不存在时，应使用此模式测试地图、点位及其他功能。

### 4. 切换到 GO2 安全占位模式

```powershell
curl.exe -sS -X POST "http://192.168.31.135:5000/api/base_mode/switch?mode=go2"
```

当前预期：

```text
mode=GO2
ready=false
reason=GO2_DRIVER_NOT_CONFIGURED
teleopEnabled=false
managedScoutRunning=false
```

这不是 GO2 驱动启动命令，只用于确保 Scout 不运行并明确当前选择的底盘类型。

## 摇杆启停命令

只有 `SCOUT + ready=true + managedScoutRunning=true` 时才允许启用摇杆。

### 启用摇杆

```powershell
curl.exe -sS "http://192.168.31.135:5000/api/teleop_key/enable?enabled=true"
```

### 立即禁用摇杆并发布零速

```powershell
curl.exe -sS "http://192.168.31.135:5000/api/teleop_key/enable?enabled=false"
```

### 查询摇杆状态

```powershell
curl.exe -sS "http://192.168.31.135:5000/api/teleop_key/status"
```

## Jetson 本机调用

SSH 登录 Jetson 后，把地址改成 `127.0.0.1`：

```bash
curl -sS http://127.0.0.1:5000/api/base_mode/status
curl -sS -X POST 'http://127.0.0.1:5000/api/base_mode/switch?mode=scout'
curl -sS -X POST 'http://127.0.0.1:5000/api/base_mode/switch?mode=none'
curl -sS -X POST 'http://127.0.0.1:5000/api/base_mode/switch?mode=go2'
```

## CAN 排障命令

模式接口在切换到 Scout 时会尝试激活并检查 `can0`。只有排障时才需要手动执行：

```bash
sudo ip link set can0 up type can bitrate 500000
ip -details -statistics link show can0
timeout 3 candump can0
```

如果激活命令返回：

```text
RTNETLINK answers: Device or resource busy
```

不代表 CAN 一定异常。继续检查 `ip -details link show can0`；若接口为 `UP`、CAN 状态为 `ERROR-ACTIVE`、bitrate 为 `500000`，说明接口已激活。`candump` 仍需看到持续接收报文，才能证明 BOX、小车供电和 CAN 通信链路完整。

## ROS1 状态检查

```bash
source /opt/ros/noetic/setup.bash
source /home/jetson/Scout_mini_navigation/install/setup.bash
rosnode list | grep scout_base_node
rostopic echo -n 1 /scout_status
```

重点检查：

```text
control_mode: 1
fault_code: 0
```

## 原始 roslaunch（只用于排障）

宿主机路径：

```bash
roslaunch /home/jetson/Scout_mini_navigation/install/share/scout_base/launch/scout_mini_base.launch \
  port_name:=can0 \
  is_scout_mini:=true \
  is_scout_omni:=false \
  simulated_robot:=false \
  pub_tf:=true
```

容器内对应路径为：

```text
/Scout_mini_navigation/install/share/scout_base/launch/scout_mini_base.launch
```

正常操作不要手动执行该 launch。手动启动的外部 `/scout_base_node` 不受 FastAPI 管理，随后调用 Scout 模式接口可能返回 `SCOUT_NODE_ALREADY_RUNNING`。

## 推荐操作顺序

1. 小车、BOX、Jetson 均上电并连接。
2. 查询 `/api/base_mode/status`。
3. 调用 `mode=scout`，确认 `ready=true`。
4. 再启用 teleop，并进行低速、空旷环境测试。
5. 测试结束先禁用 teleop，再切换到 `mode=none`。
6. 小车断电、只测试导航前端或准备切换 GO2 时，保持 `NONE` 或使用 GO2 安全占位模式。
