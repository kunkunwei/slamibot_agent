# ADR-0002：D360 使用双 rosbridge 固定端口职责

- 日期：2026-08-19
- 状态：ACCEPTED_AND_DEPLOYED
- 生命周期：CURRENT（ROS1 + Ubuntu 20.04）
- migration: false

## 背景

`core` 和 `scout-nav` 共用宿主机 ROS Master。两套 rosbridge 原先都使用默认节点名
`/rosbridge_websocket`，重启 `scout-nav` 时会发生同名节点互踢。客户端配置也出现分裂：APP
代码虽然展示 9090，运行时默认值却被改成 19090；WEB `/rosbridge` 同样被反代到 19090。

## 问题

需要同时满足以下约束：APP/WEB 保持历史客户端兼容端口，nav_api 有独立的内部连接，且单独
重启 `scout-nav` 不影响客户端 rosbridge。

## 选择

- Android APP 的地图、点云、位姿、控制等全部 ROS 功能统一连接 `ws://<Jetson>:9090`。
- 浏览器 WEB 使用同源 `/rosbridge`，Nginx 将其反代到 `127.0.0.1:9090`。
- `core` 提供 9090，节点名保持 `/rosbridge_websocket`。
- FastAPI/nav_api 仅连接 `127.0.0.1:19090`。
- `scout-nav` 提供 19090，节点名固定为 `/scout_nav_rosbridge`。
- 两套 rosbridge 共享一个 ROS Master；端口区分调用职责，不隔离 Topic/Service 数据域。

## 原因

该方案兼容旧版客户端约定，同时把导航后端内部依赖留在 19090；唯一节点名解决同名 shutdown，
无需修改 Topic、Service、消息格式、Docker host 网络或 ROS Master。

## 影响

- APP 和 WEB 的客户端配置必须始终指向 9090。
- FastAPI `/health` 的 `rosbridgeConnected` 只表示 19090 内部链路状态。
- 故障排查必须分别检查 9090 客户端链路与 19090 nav_api 链路。
- `scout-nav` 启动检查同时验证进程、ROS 节点和 TCP 19090，避免容器显示 Up 但 rosbridge 已退出。

## 部署证据

2026-08-19 Jetson 只读核验：

- 80、5000、9090、19090 均监听；
- `/rosbridge_websocket` 与 `/scout_nav_rosbridge` 同时存在；
- Nginx `/rosbridge` 最终上游为 `127.0.0.1:9090`；
- `/health` 返回 `rosbridgeConnected:true`；
- 当前容器使用 `scout-nav:dual-rosbridge-20260819`；停止状态的回滚容器为
  `scout-nav-pre-dual-20260819`。

## 未完成验收

APP 默认端口改动仍未提交；APP 真机与 WEB 的地图、点云、位姿、控制尚未完成全部端到端联调。

## 替代方案

- 所有调用方共用单个 9090：减少进程，但改变 nav_api 已有内部依赖和故障域，未采用。
- APP/WEB 继续使用 19090：破坏旧版客户端 9090 兼容约定，未采用。
- 客户端自动回退 9090/19090：会掩盖配置错误并增加状态复杂度，未采用。

## 详细设计

见 `docs/superpowers/specs/2026-08-19-d360-dual-rosbridge-design.md`。
