# APP/Web 地图与点云不显示：快速诊断记录

- 记录日期：2026-08-21
- 适用范围：SLAMIBot APP、Web、Jetson `scout-nav`、ROS1 导航
- 目标：新会话遇到“2D 栅格地图不显示 / 3D 点云不显示”时，先按最小路径定位，禁止一开始做全局代码或容器恢复。

## 典型现象

- APP/Web 能打开，但没有 `/map` 栅格地图；或没有 `/global_cloud_navigation` 3D 点云。
- rosbridge/WebSocket 可能显示已连接，但这不代表 ROS 发布节点真实运行。
- ROS Master 可能保留 stale node 注册，必须同时检查真实进程和消息。

## 快速诊断顺序（ROS1）

1. 确认容器和后端健康：
   ```bash
   docker ps --filter name=scout-nav
   curl -fsS http://127.0.0.1:5000/health
   ```
2. 确认当前激活地图和地图资源：
   ```bash
   curl -fsS http://127.0.0.1:5000/api/map/active
   ```
   记录地图名，并检查对应目录是否有：
   ```text
   <map>.yaml / <map>.pgm
   <map>.pcd / <map>_display.pcd
   ```
3. 检查真实 ROS 发布进程，不只看 `rosnode list`：
   ```bash
   pgrep -af 'map_server|amcl|move_base|pcd_map_publisher'
   rosnode info /map_server
   rosnode info /pcd_map_publisher_*
   ```
4. 检查消息是否真实产生：
   ```bash
   timeout 5 rostopic echo -n 1 /map
   timeout 5 rostopic echo -n 1 /global_cloud_navigation
   rostopic info /map
   rostopic info /global_cloud_navigation
   ```
5. 仅在确认资源完整且节点缺失时，通过既有导航/地图启动接口恢复；不要先重启整个容器或覆盖源码。

## 已确认案例（2026-08-21）

- 激活 `dinggu7_5` 时，`dinggu7_5.pcd` 与 `dinggu7_5_display.pcd` 不存在，点云 publisher 未真实运行；ROS Master 的节点名是 stale registration。
- 切换到具有完整 PCD 资源的 `dinggu7_6` 后，调用现有导航启动接口自动拉起 publisher。
- `/global_cloud_navigation` 发布 `sensor_msgs/PointCloud2`，`frame_id=map`，约 332384 点，静态点云心跳约 0.1 Hz，用户确认 3D 点云恢复。

## 处理边界

- 不得把不同地图的 PCD 强行发布到当前 2D 地图。
- 不修改/删除地图、数据库或未上传云端资源；若必须恢复这类资源，单独建立任务并先确认来源。
- 不因单个显示问题覆盖整个容器、替换镜像或遍历所有仓库。
- 代码恢复必须以云端 Git 提交为基线；只有现有启动机制无法恢复时才进入代码修改。

## 验收

- `/map` 或 `/global_cloud_navigation` 有真实消息；
- 对应 publisher 进程存在且 `rosnode info` 可通信；
- APP/Web 页面恢复显示；
- 将诊断结论和未解决风险写入工作台，不只留在对话中。
