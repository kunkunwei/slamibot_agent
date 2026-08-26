# 手动遥控延迟快速验证（ROS1 / D360）

- task: `TASK-2026-08-25-002`
- technology: ROS1 Noetic CURRENT
- status: EXPERIMENT_A_CONFIRMED
- scope: 用户手动操作 + APP设备ADB只读诊断
- forbidden: 不SSH、不重启容器、不改ROS参数、不部署、不执行`rosnode cleanup`，不混入ROS2/DDS QoS。

## 链路

```text
APP 25Hz /cmd_vel_web -> ws://<Jetson-IP>:9090 -> core rosbridge
-> FastAPI teleop/roslibpy（内部 :19090）-> 50Hz /cmd_vel
-> scout_base_node -> CAN -> Scout mini
```

- 手动导航ROS WebSocket固定使用端口`9090`：Wi-Fi为`192.168.31.135:9090`，图传为`192.168.144.87:9090`。
- APP为控制、`/map`和`/global_cloud_navigation`分别创建独立WebSocket；Socket虽独立，仍竞争同一`ar_net0`、图传物理链路和Jetson `eth2`。
- APP仅暂停点云renderer不会减少网络流量；低延迟模式必须暂停点云网络订阅或断开其专用WebSocket。

## 基线证据

- Wi-Fi：遥控顺畅；Ping前12样本多为`1.4–8.7ms`，`seq13–22`曾突发`175–324ms`后恢复，无完整统计行。
- 图传：Ping前10样本约`306–406ms`，主要`395–406ms`，启停明显延迟，无完整统计行。
- 图传基线9090共有3条`ESTAB`：`43634`、`43612`、`43622`。
- 控制候选`43612`：Send-Q最终`8018`，`notsent`最终`729`，RTT最终`1099.28ms`，RTO最终`2832ms`，`unacked=8`；`retrans=0/2`样本内未见增长。
- 大接收流`43634`：`bytes_received`约144MB增至150MB，RTT约`426–480ms`，最终`rcv_rtt=1188ms`。
- `43622`：接收约1.3MB，RTT约`414–470ms`。

## 实验A：仅停止点云网络订阅

### 单变量配置

```text
/global_cloud_navigation：关闭APP网络订阅
/map：保持订阅
/cmd_vel_web：保持25Hz
ROS侧map_server和点云发布节点：不停止
```

### 2026-08-25结果

- 用户体验：几乎无延迟、手感好；此项是用户体验记录，不替代帧级测量。
- 9090连接由3条降至2条：`40690`、`40686`。
- 控制候选`40686`：
  - RTT约`36.0–41.5ms`
  - RTO约`240–244ms`
  - Send-Q样本：`0/146/328/364/546/368/183`，峰值`546`
  - `notsent`仅一次`184`
  - 未见Send-Q或notsent持续增长
- 另一连接`40690`：RTT约`37ms`，流量极少。

### 基线对比

| 指标 | 基线控制候选43612 | 实验A控制候选40686 | 结果 |
|---|---:|---:|---|
| RTT | 最终1099.28ms | 约36.0–41.5ms | 显著下降 |
| RTO | 最终2832ms | 约240–244ms | 显著下降 |
| Send-Q | 最终8018 | 峰值546，未持续增长 | 积压消失 |
| notsent | 最终729 | 仅一次184 | 显著下降 |
| 9090连接数 | 3 | 2 | 点云专用连接消失 |
| 用户体验 | 启停明显延迟 | 几乎无延迟、手感好 | 与网络指标一致 |

## 结论与停止条件

1. 单变量A/B已确认`/global_cloud_navigation`点云大流是图传遥控延迟主因。
2. 保留`/map`和25Hz `/cmd_vel_web`即可获得良好手感，不需要通过停地图或降频恢复当前低延迟。
3. **停止实验B/C/D**：不再进行“停地图”、`25Hz -> 15Hz`或`25Hz -> 10Hz`实验，避免引入无必要变量。
4. 后退更慢仍为`NEEDS_CONFIRMATION`；当前网络证据不显示方向差异。

## 正式修复验收要求

1. 进入“手动低延迟模式”时，APP停止`/global_cloud_navigation`网络订阅或断开点云专用WebSocket；仅调用renderer pause不算通过。
2. 退出手动模式、进入需要显示点云的页面或显式打开点云显示时，按需恢复订阅；避免重复连接和自动重连把点云提前恢复。
3. `/map`继续保持当前行为；`/cmd_vel_web`继续25Hz。
4. 复测应看到2条9090连接，控制候选RTT/RTO接近实验A量级，Send-Q/notsent不持续增长，摇杆启停无明显延迟。
5. 若点云恢复显示，再确认只生成一条点云WebSocket，退出后连接能正确释放。

## 后续安全加固（非本次必要条件）

- 在控制WebSocket增加OkHttp `queueSize()`观测。
- 实现Twist latest-only，确保旧方向命令不排队重放，零速不位于历史命令之后。
- 增加控制命令过期丢弃和底盘watchdog。
- `TCP_NODELAY`只作为逐段补充，不是本次根因修复。

## 如需继续量化方向差异

仅当后续仍报告“后退更慢”时，再分别执行10轮前进和10轮后退，从静止开始，用120/240fps录像统计启动/停止中位数、最小值和最大值；不要从前进直接切后退，以免混入制动与换向保护。
