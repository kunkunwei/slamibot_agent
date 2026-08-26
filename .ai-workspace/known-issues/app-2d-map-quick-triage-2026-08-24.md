# APP/Web 无法接收 2D 栅格地图：快速排查手册

- 适用对象：SLAMIBot D360、ROS1 Noetic、Jetson、`core`、`scout-nav`
- 典型现象：APP 和 Web 都没有 2D 栅格地图，但 3D 点云和手动遥控正常。
- 更新时间：2026-08-25
- 运行原则：默认只读；先确认事实，再决定是否执行模式切换。不要把此问题误判为 OAK/RTSP 或雷达问题。

## 工作台快速入口

下次遇到“APP/Web 没有 2D 地图，但 3D 点云和遥控正常”时，先读取本文件，不要立即扫描所有仓库、全量日志或修改代码。只按本手册的最小顺序执行：

```text
1. docker ps
2. rostopic info /map
3. 检查 /map 是否有真实 Publisher
4. 检查 launch/status 与 map_server 进程
5. 检查 /map 首帧
6. 只有 /map 正常后，才查 9090/Nginx/WebSocket/APP
```

优先关键词：`/map`、`nav_msgs/OccupancyGrid`、`Publishers: None`、`map_server`、`navigation_running`、`9090`。

## 一、先记住判断原则

APP/Web 的 2D 地图都来自 ROS1 的 `/map`：

```text
/map
类型：nav_msgs/OccupancyGrid
入口：core 容器内 ROS Master/rosbridge
APP：通常直连 Jetson:9090
Web：浏览器 /rosbridge，经 Nginx 转发到 core:9090
```

3D 点云使用独立链路（例如 `/global_cloud_navigation`），点云正常不代表 `/map` 正常。

**最关键的判断：**

```text
/map 存在 + Publishers: None = 地图源没有启动
/map 有 Publisher 但无消息 = 地图源异常或消息链路异常
/map 有消息但 APP/Web 无图 = rosbridge、Nginx、客户端订阅或协议问题
```

## 二、最小排查路径

### 1. 确认容器状态

在 Jetson 主机执行：

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
```

至少关注：`core`、`scout-nav`。容器处于 `Up` 只说明容器存在，不代表导航节点已经启动。

### 2. 检查 `/map` 是否有发布者

```bash
docker exec core bash -lc '
source /opt/ros/noetic/setup.bash
rostopic list | grep -E "^/map$|map_metadata|costmap"
rostopic type /map
rostopic info /map
'
```

正常最低要求：

```text
Type: nav_msgs/OccupancyGrid
Publishers:
- /map_server ...
```

如果结果是：

```text
Type: nav_msgs/OccupancyGrid
Publishers: None
Subscribers:
- /rosbridge_websocket ...
```

结论是 **core/rosbridge 已经在等地图，但没有任何节点发布地图**。此时不要先改 APP/Web。

### 3. 检查导航节点和真实进程

```bash
docker exec scout-nav bash -lc '
source /opt/ros/noetic/setup.bash
rosnode list | grep -Ei "map_server|move_base|amcl|nav|pcd"
ps -ef | grep -Ei "roslaunch|map_server|move_base|amcl|nav_multi|pcd_map_publisher" | grep -v grep
'
```

重点确认：

- `/map_server` 是否存在；
- `move_base`、`amcl` 是否存在（取决于当前导航模式）；
- `nav_multi_node.py` 是否只是 API/模式管理进程；
- `pcd_map_publisher.py` 只发布 3D PCD，不等价于 2D `map_server`。

只看 `rosnode list` 不够。ROS Master 可能残留 stale node 注册，必须结合 `ps -ef` 和实际消息确认。

### 4. 检查导航模式生命周期

```bash
curl -s http://127.0.0.1:5000/api/launch/status
```

重点字段：

```json
{
  "current_mode": "navigation",
  "base_running": true,
  "navigation_running": true,
  "pcd_running": true
}
```

若出现类似：

```json
{
  "current_mode": "idle",
  "base_running": false,
  "mapping_running": false,
  "navigation_running": false,
  "pcd_running": true
}
```

说明只有 PCD/3D 资源链路运行，2D 导航生命周期没有启动，因此 `/map` 没有 Publisher。

### 5. 检查 `/map` 是否真的有消息

确认存在 Publisher 后再执行：

```bash
docker exec core bash -lc '
source /opt/ros/noetic/setup.bash
timeout 10 rostopic echo -n 1 /map
'
```

也可以观察频率：

```bash
docker exec core bash -lc '
source /opt/ros/noetic/setup.bash
timeout 10 rostopic hz /map
'
```

静态地图不一定持续高频发布，但必须能够收到首帧；`rostopic echo -n 1 /map` 长时间没有输出，仍视为上游异常。

## 三、恢复方式

### 推荐：使用项目既有模式接口

如果已经确认 `/map` 没有 Publisher，先查清项目规定的导航入口和当前模式接口，再执行模式切换。不要直接 `docker restart scout-nav`，也不要手工同时启动多个 `roslaunch`，避免底盘、TF、地图和导航节点重复启动。

本次实测的恢复路径是：

```text
idle
  -> 建图模式（mapping）
  -> 导航模式（navigation）
```

切换后重新检查：

```bash
curl -s http://127.0.0.1:5000/api/launch/status

docker exec core bash -lc '
source /opt/ros/noetic/setup.bash
rostopic info /map
timeout 10 rostopic echo -n 1 /map
'
```

确认 `Publishers` 出现 `/map_server` 且能收到 `nav_msgs/OccupancyGrid` 后，再打开 APP/Web 验证。

### 不建议的操作

```text
不要先改 APP/Web 代码；
不要把 /global_cloud_navigation 当成 /map；
不要先检查 OAK 推流或普通 /dev/video*；
不要直接删除相机节点、删除容器或覆盖地图文件；
不要把 ROS1 问题改用 ROS2 命令排查。
```

## 四、如果 `/map` 正常但 APP/Web 仍无图

按以下顺序继续：

```bash
# core rosbridge 是否监听
sudo ss -ltnp | grep ':9090'

# Jetson Web 入口的 Nginx /rosbridge 是否可用
curl -i --max-time 5 http://127.0.0.1/rosbridge

# Web 页面所在端口（仅确认页面，不等于 WebSocket 正常）
curl -I --max-time 5 http://127.0.0.1/app/
```

然后分别检查：

1. Web 浏览器开发者工具 → Network → WebSocket：是否成功升级、是否收到 `/map` 订阅响应和消息；
2. APP 日志：是否连接 `ws://<Jetson-IP>:9090`，是否订阅 `/map`；
3. APP 使用的消息协议是否为 `cbor-raw`，以及 JSON fallback 是否触发；
4. 是否把 `19090` 误当成 APP/Web 的 rosbridge 端口。`19090` 是 `scout-nav` 内部 FastAPI/nav_api 端口，APP/Web 地图入口是 `9090`。

## 五、点击点位后右下角 `timeout` 的分支

如果地图已经显示，但 APP 打开点位时右下角显示 `timeout`，这是新的问题，不再归因于 `/map` 缺失。执行：

```bash
docker exec scout-nav bash -lc '
source /opt/ros/noetic/setup.bash
rosnode list | grep -Ei "nav|move_base|map_server|amcl"
rosservice list | grep -Ei "nav|goal|waypoint|point|task|map"
'

docker logs --since "10 minutes ago" scout-nav 2>&1 | \
grep -Ei 'point|waypoint|task|goal|nav|timeout|timed out|error|failed|exception|map'
```

判断：

- 有 `map_server` 但点位请求日志报超时：优先查点位 API、导航 action/service 响应；
- 没有 `move_base` 或目标导航服务：导航模式状态可能只是管理状态，点位任务服务未真正就绪；
- 日志完全没有点位请求：检查 APP 是否连接正确的 Jetson 地址和接口端口；不要只看页面是否能打开。

## 六、最终验收清单

```text
[ ] core 和 scout-nav 容器正常
[ ] /map 类型为 nav_msgs/OccupancyGrid
[ ] /map 有真实 Publisher（通常为 /map_server）
[ ] rostopic echo -n 1 /map 能收到首帧
[ ] APP/Web 的 rosbridge 均使用 9090
[ ] WebSocket 升级成功且收到 /map 消息
[ ] APP 页面显示地图
[ ] 点位页面请求不再 timeout，或已单独记录其 API/导航错误
```

## 七、已确认案例

### 案例 A：2026-08-24，导航生命周期未启动

初始 `launch/status` 为 `idle`，但 `pcd_running=true`，同时 `/map` 的 `Publishers` 为 `None`；因此 APP 和 Web 都无法收到 2D 地图。先点击建图模式，再点击导航模式后，状态变为 `navigation`、`base_running=true`、`navigation_running=true`、`pcd_running=true`，APP/Web 恢复收到 2D 地图。

结论：根因是 **2D 导航生命周期没有启动**，不是 3D 点云链路或客户端地图渲染问题。

### 案例 B：2026-08-25，Jetson/容器重启后没有自动恢复导航模式

现场首先修复了 `nav_multi_node.py` 缺少执行权限导致的容器重启循环。`scout-nav` 随后能够正常启动：

```text
rosbridge OK
nav_multi_node OK
Nginx OK
FastAPI OK
rosbridgeConnected=true
```

但 APP 仍收不到 2D 栅格地图。按本手册的最小路径检查得到：

```text
scout-nav: Up
/map: nav_msgs/OccupancyGrid
/map Publishers: None
current_mode: idle
base_running: false
navigation_running: false
pcd_running: true
```

真实进程中只有：

```text
/nav_multi
/pcd_map_publisher_...
```

没有：

```text
/map_server
/amcl
/move_base
```

因此本次调用链为：

```text
Jetson/容器重启
  -> scout-nav 基础服务正常启动
  -> 后端模式状态回到 idle
  -> 导航 launch 没有自动恢复
  -> map_server 没有启动
  -> /map 没有 Publisher
  -> APP/Web 无 2D 栅格地图
```

恢复入口使用现有模式 API：

```bash
curl -sS http://127.0.0.1:5000/api/control/mode/navigation
```

然后验证：

```bash
curl -sS http://127.0.0.1:5000/api/launch/status
rostopic info /map
timeout 10 rostopic echo -n 1 /map
```

预期至少满足：

```text
current_mode=navigation
navigation_running=true
/map Publisher=/map_server
/map 能收到首帧
```

## 八、如何判断是不是“残留进程/ROS Master 假死”

不要看到“容器重启后无地图”就直接判断为残留进程。先对照下面的证据：

| 现场证据 | 更可能的结论 |
|---|---|
| `launch/status=idle`，没有 `map_server` 进程，`/map Publishers: None` | 导航生命周期未启动，不是残留进程 |
| `rosnode list` 有 `/map_server`，但 `ps` 中没有对应进程，`rosnode ping` 失败 | ROS Master 可能存在 stale registration |
| 新旧多个 `map_server`/`move_base` 进程同时存在 | 可能存在重复启动或未清理进程 |
| `/map` 有健康 Publisher 且能收到首帧，但 APP/Web 无图 | 转查 9090、WebSocket、CBOR 和客户端订阅 |
| `/map` 有 Publisher，但 `rosnode ping` 失败且首帧超时 | 检查残留注册、节点 URI 与真实进程 |

本案例 B 中没有旧的 `map_server`、`amcl`、`move_base` 进程，也没有相应节点注册，因此**没有证据支持“残留进程导致假死”**。不要执行全局：

```bash
rosnode cleanup
docker restart scout-nav
```

应先通过已有导航模式接口恢复生命周期。

## 九、重启后的固定快速检查

以后重启 Jetson 或 `scout-nav` 后，按以下顺序检查，不进行全局文件搜索：

```bash
# 1. 容器是否正常
docker ps --filter name=scout-nav

# 2. 后端服务与模式状态
curl -sS http://127.0.0.1:5000/health
curl -sS http://127.0.0.1:5000/api/launch/status

# 3. 地图发布者
rostopic info /map

# 4. 真实导航进程
docker exec scout-nav bash -lc '
source /opt/ros/noetic/setup.bash
rosnode list | grep -Ei "map_server|amcl|move_base|nav_multi"
ps -ef | grep -Ei "map_server|amcl|move_base|nav_multi" | grep -v grep
'
```

快速判断：

```text
容器未启动              -> 先看容器入口日志
容器正常但 mode=idle     -> 切换到 navigation
mode=navigation 无 map   -> 查 map_server/launch 日志
/map 正常但 APP 无图     -> 查 9090/WebSocket/APP
```

