# 接口：外协 3D 导航 Web/ROS 契约（Flask :9000）

> 来源：`/home/jetson/nav_frontend_redesign/通信接口清单.md`（其参考后端 = `/home/jetson/docker_ws_backup/src/robot_web_controller`）
> 前端重构原则：**以现有后端为准，重构前端不改后端协议**。

## 三条通信通道
| 通道 | 地址 | 协议 | 用途 |
|---|---|---|---|
| REST API | `http://<host>:9000/api/*` | HTTP + JSON | 增删改查、模式切换、任务下发 |
| ROS 实时 | `ws://<host>:19090` | rosbridge WebSocket（roslibjs + ros3djs + tf2_web_republisher） | 实时位姿/点云/TF/速度/目标点 |
| 视频流 | `http://<host>:9000/api/go2/stream/{visible,infrared}` | MJPEG | 可见光 / 红外，`<img>` 直接渲染 |

- 认证：HTTP Basic Auth（`admin`）+ CORS（`supports_credentials=True`）
- 通用返回体：`{ "success": bool, "data": any, "msg": str }`

## REST 清单摘录
- **状态** `/api/status/` → `pose{position,orientation,yaw}`、`power{percent,voltage,isCharging}`、`nav{navTaskProgress,currentTarget}`、`control`、`mapName`、`mode(0导航/1建图)`；建议 1Hz 轮询
- **运动/模式** `/api/control/mode/mapping`（切建图）/ `navigation`（切导航）/ `pub_recharger_flag`（回充）；
  `/api/teleop_key/{status,enable,send}`（键盘遥控，底层发 `/cmd_vel_web`）
- **建图/导航生命周期** `/api/launch/{mapping,navigation}/start|stop`、`/api/launch/status`
- **地图与点位** `/api/map/save?mapName=`（保存）、`/patch?mapName=`（增量建图）、`/upload`、`/config/upload`、
  `/prohibition_areas/upload`、`/switch?mapName=`；`/nav_custom`（`{x,y,z,yaw}`）、`/nav_multi?cruise=`（点位批量）、
  `/nav_multi/cancel?stop_recharger=1`、`/set_pose`（`{x,y,z,qx,qy,qz,qw}`）；`/api/launch/clear-pointcloud-cache`
- **来源后端**：Flask `robot_web_controller.py`，蓝图 status/control/map/settings/action；`static/` 以 `/app` 提供前端静态资源

## 备注
- 该契约是**外协 3D 导航**（Go2 + Livox MID360 + FAST-LIO + global/local planner）的接口；与自研 3D（kn_nav）和 2D（Scout mini）的接口分离，勿混。