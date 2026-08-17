# D360 2D 导航问题定位 —— 资料移交文档（给 AI）

> 机器人：松灵 Scout Mini 四轮差速小车  
> 激光雷达：Livox Mid-360（3D 点云）  
> 导航：move_base（TEB 局部规划 + GlobalPlanner 全局规划）+ AMCL 定位  
> 问题：窄口/窄道场景中规划失败（5 秒超时）  
> 图片/截图：无；日志：无（系统未在运行，只提供代码与配置）

---

## 1. 3D 点云 → 2D 地图的完整代码

### 1.1 点云采集（Livox Mid-360）
- 驱动包：`livox_ros_driver2`（ROS1 版）
- 容器：`firmware-sensors`（镜像 `slamibot_d360_firmware:latest`）
- 发布 Topic：`/livox/lidar`（`sensor_msgs/PointCloud2`）、`/livox/imu`（`sensor_msgs/Imu`）

### 1.2 点云重映射（livox_repub）
```xml
<node pkg="livox_repub" type="livox_repub" name="livox_repub" output="screen">
  <remap from="/livox/lidar" to="/livox/lidar" />
</node>
```
发布 Topic：`/livox_pcl0`（标准 PointCloud2）

### 1.3 3D 点云 → 2D 激光扫描（pointcloud_to_laserscan）
```xml
<node pkg="pointcloud_to_laserscan" type="pointcloud_to_laserscan_node"
      name="pointcloud_to_laserscan">
  <remap from="cloud_in" to="/livox_pcl0"/>
  <rosparam>
    target_frame: base_link
    transform_tolerance: 0.01
    min_height: -0.1          # 过滤地面以下
    max_height: 0.5            # 过滤 0.5m 以上
    angle_min: -3.1415926      # -π
    angle_max: 3.1415926       #  π（全向 360°）
    angle_increment: 0.006     # ≈0.34°
    scan_time: 0.1
    range_min: 0.1
    range_max: 40
    use_inf: true
    concurrency_level: 1
  </rosparam>
</node>
```
发布 Topic：`/scan`（`sensor_msgs/LaserScan`）

### 1.4 PCD 地图 → 2D 栅格地图（pcd_to_map.py）
- 路径：`src/my_nav/maps/pcd_to_map.py`
- 用法：
```bash
python3 pcd_to_map.py api_map/dinggu7_2/dinggu7_2_display.pcd \
  -o api_map/dinggu7_2/dinggu7_2_map__display_auto_fill --fill-free
```
- 依赖：NumPy、SciPy（`--fill-free` 时用 SciPy 填充空洞）
- PCD 来源：FAST-LIO 建图产出（`src/FAST_LIO_gravity_align/PCD/`）
- 建图 launch：`roslaunch my_nav fastlio_mapping.launch`

### 1.5 完整启动链路
```bash
# 1. 配置 CAN 底盘
sudo ip link set can0 up type can bitrate 500000
timeout 3 candump can0

# 2. 启动底盘 + 雷达 → scan 链路
roslaunch my_nav lidar_to_scan.launch

# 3. 启动导航（地图 + AMCL + move_base）
roslaunch my_nav my_nav_launch.launch
```

---

## 2. Mid-360 点云输入信息

| 字段 | 值 |
|---|---|
| Topic | `/livox/lidar`（PointCloud2） |
| 重映射后 | `/livox_pcl0`（由 livox_repub 发布） |
| IMU Topic | `/livox/imu` |
| 雷达 Frame | `laser`（由 `scout_description/urdf/livox_mid360.urdf.xacro` 定义，经 `robot_state_publisher` 发布 TF） |
| 雷达安装位置 | 约 base_link 前方 0.166m、上方 0.14m（见 launch 中注释的 static TF） |
| 水平 FOV | 360°（angle_min/max 全向） |
| 垂直 FOV | 取 min_height=-0.1 到 max_height=0.5 做地面过滤 |

---

## 3. 当前系统环境

| 维度 | 值 |
|---|---|
| ROS | **ROS 1 Noetic** |
| Ubuntu | 20.04.6 LTS（宿主机 Jetson；容器内同） |
| 构建 | `catkin_make install`（install 空间：`/Scout_mini_navigation/install`） |
| 导航框架 | **move_base**（ROS 1 导航栈） |
| 全局规划 | GlobalPlanner（use_dijkstra=true） |
| 局部规划 | **TEB**（TebLocalPlannerROS） |
| 定位 | AMCL（`likelihood_field` 模型） |
| 建图 | FAST-LIO（gravity_align 变体，3D） + `pcd_to_map.py`（→ 2D 栅格） |
| 底盘 | Scout Mini（CAN can0 500kbit/s） |
| 前端 | React Web（nginx，`/app/`）+ rosbridge（19090 端口，WebSocket） |
| 后端 | FastAPI（5000 端口，`nav_api` 包） |

---

## 4. 导航参数/配置

### 4.1 move_base 顶层参数
```yaml
controller_frequency: 8.0      # 与 local_costmap update_frequency 对齐
planner_frequency: 1.0
planner_patience: 5.0          # ★ 全局规划 5 秒超时（你提到的 5 秒）
controller_patience: 5.0       # ★ 局部规划 5 秒超时
oscillation_timeout: 12.0
oscillation_distance: 0.15     # 12s 内移动 < 15cm 视为振荡
```

### 4.2 全局规划器（GlobalPlanner）
```yaml
base_global_planner: global_planner/GlobalPlanner
use_dijkstra: true             # Dijkstra 比 A* 保守，路径靠窄口中心
use_grid_path: false
use_quadratic: true
allow_unknown: false
lethal_cost: 250               # < 253，INSCRIBED_INFLATED_OBSTACLE 被视为致命
neutral_cost: 66               # 偏好直线路径
cost_factor: 3.0               # 障碍代价权重
```

### 4.3 局部规划器（TEB）
```yaml
# 运动学
max_vel_x: 0.60                # 窄口降速
max_vel_x_backwards: 0.20
max_vel_theta: 0.80
acc_lim_x: 0.50
acc_lim_theta: 1.0
holonomic_robot: False         # 严格非完整（差速+原地转）

# 轨迹
dt_ref: 0.20                   # 窄道密时间柱
max_global_plan_lookahead_dist: 2.5

# 障碍物
min_obstacle_dist: 0.1
inflation_dist: 0.25
obstacle_poses_affected: 15    # 窄道墙上点多
costmap_converter_plugin: "costmap_converter::CostmapToPolygonsDBSMCCH"

# 目标
xy_goal_tolerance: 0.12
yaw_goal_tolerance: 0.15

# 优化权重
weight_obstacle: 50.0          # 强避障
weight_inflation: 8
weight_viapoint: 1             # 强贴合全局路径
weight_optimaltime: 3.0
weight_kinematics_nh: 1000     # 强制非完整
```

### 4.4 代价地图（Costmap）

**机器人足迹**（多边形，单位 m）：
```
[[0.306, 0.29], [0.306, -0.29], [-0.306, -0.29], [-0.306, 0.29]]
```
即 0.61m × 0.58m 矩形。

**共用参数**：
```yaml
obstacle_range: 4
raytrace_range: 10
max_obstacle_height: 1.0
min_obstacle_height: 0.0       # 不过滤低障，防漏路沿/台阶
inflation_radius: 0.06
cost_scaling_factor: 12.0
transform_tolerance: 0.5
observation_sources: scan      # 输入 /scan（LaserScan）
```

**局部代价地图**：
```yaml
global_frame: odom
update_frequency: 12.0
rolling_window: true
width: 4.0 / height: 4.0
resolution: 0.05
inflation_radius: 0.05         # 注意：局部 0.05，全局 0.33
footprint_clearing_enabled: true
```

**全局代价地图**：
```yaml
global_frame: map
update_frequency: 1.5
static_map: true
resolution: 0.05
inflation_radius: 0.33         # 注意：全局 0.33，局部 0.05
cost_scaling_factor: 1
footprint_clearing_enabled: true
```

### 4.5 Recovery 行为
```yaml
recovery_behaviors:
  - { name: conservative_reset, type: clear_costmap_recovery/ClearCostmapRecovery }
  - { name: aggressive_reset,   type: clear_costmap_recovery/ClearCostmapRecovery }
# 注意：已移除 RotateRecovery（窄口里旋转必撞）
conservative_reset/reset_distance: 1.5
aggressive_reset/reset_distance: 0.5
```

---

## 5. TF / 坐标系关系

```
map ──(AMCL)──→ odom ──(scout_base 里程计)──→ base_link ──(robot_state_publisher)──→ laser
```

| Frame | 发布者 | 说明 |
|---|---|---|
| `map` | AMCL | 全局地图坐标系 |
| `odom` | scout_base（底盘里程计） | 里程计坐标系 |
| `base_link` | scout_base | 机器人本体中心 |
| `laser` | robot_state_publisher（从 URDF） | Livox Mid-360 雷达坐标系 |

- AMCL 参数：`global_frame_id=map`、`odom_frame_id=odom`、`base_frame_id=base_link`
- 雷达外参（从 launch 中注释的 static TF）：相对 base_link 前方 0.166m、上方 0.14m、俯仰 0.349 rad（约 20°）；实际由 URDF 定义、`robot_state_publisher` 发布

---

## 6. 错误地图截图（无）

系统未在运行，无实际截图。请结合 costmap 配置和 footprint 尺寸自行模拟。

---

## 7. 真实环境对应情况（无）

无现场照片。窄口场景为 0.46m 宽的室外走廊（参数文件注释提及）。

---

## 8. 规划失败时的日志（无）

系统未在运行，无实际日志。已知超时参数：
- `planner_patience: 5.0`（全局规划 5 秒超时）
- `controller_patience: 5.0`（局部控制 5 秒超时）
- 典型错误关键词：`No valid path`、`planner timeout`、`Failed to get a plan`

---

## 附录：仓库地址

| 仓库 | 地址 |
|---|---|
| 2D 导航（本系统） | `https://github.com/kunkunwei/Scout_mini_navigation` |
| 自研 3D 导航 | `https://github.com/kunkunwei/3d_nav` |
| 外协 3D 导航 | `https://github.com/kunkunwei/movebase_3d_web` |
| D360 驱动框架 | `https://github.com/kunkunwei/SLAMIBOT_D360_Framework` |
| 前端 APP | `https://github.com/electech6/SLAMIBotApp` |
| STM32 固件 | `https://github.com/electech6/slamibot_stm32` |