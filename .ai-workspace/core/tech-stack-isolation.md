# 技术栈隔离（Tech Stack Isolation）

ROS1 与 ROS2 是两套完全不同的系统。**严禁混淆**。这是本工作区最核心的约束之一。

## 隔离铁律
1. ROS1 项目只能使用 ROS1 的命令、包管理、launch、参数、Topic/Service/Action、依赖。
2. ROS2 项目只能使用 ROS2 的命令、包管理、launch、参数、Topic/Service/Action、依赖、DDS/RMW。
3. 一个任务只能面向一个栈（`technology: ros1` 或 `ros2`）；涉及两者时必须是显式的迁移/联调专项任务。
4. 对任何文件/命令/脚本/配置，**无法确认属于 ROS1 还是 ROS2 时，先检查确认，绝不猜测**。

## 判据（如何确认一个包/文件属于哪套）
- 读 `package.xml`：`<build_type>catkin</build_type>` → ROS1；`ament_cmake` / `ament_python` → ROS2。
- 读 `CMakeLists.txt`：`find_package(catkin ...)` → ROS1；`find_package(ament_cmake ...)` / `ament_package()` → ROS2。
- launch：`.launch` 通常 ROS1；`*.launch.py` / `*.launch.xml` / `*.launch.yaml` 且用 `ros2 launch` → ROS2。
- 命令：`roscore` / `rosrun` / `roslaunch` / `rosparam` / `rostopic` → ROS1；
  `ros2 run` / `ros2 launch` / `ros2 topic` / `ros2 param` → ROS2。
- 构建：`catkin_make` / `catkin build` → ROS1；`colcon build` → ROS2。

## 事实源隔离
- ROS1 事实 → `facts/navigation_ros1_profile.yaml`，记录 Ubuntu 20.04、ROS1 版本、rosbridge、关键 Topic/Node/TF/参数、启动方式、Docker 环境、依赖。
- ROS2 事实 → `facts/navigation_ros2_profile.yaml`，记录 Ubuntu/ROS2 版本、Node/Topic/TF/参数、Launch、DDS/RMW、Docker 环境、依赖。
- 两套事实源物理分开，禁止把 ROS1 的 Topic 写进 ROS2 文件。

## 命令 / 包管理 / 参数 / 消息模型对照（速查）

| 维度 | ROS1 | ROS2 |
|---|---|---|
| 构建 | catkin_make / catkin build | colcon build |
| 运行 | roscore, rosrun, roslaunch | ros2 run, ros2 launch |
| 参数 | rosparam / ROS Parameter Server（全局） | ros2 param（节点级） |
| 通信 | Topic / Service（sync） | Topic / Service（sync）/ Action（async，首选长任务） |
| 消息定义 | msg / srv | msg / srv / action |
| 中间件 | TCPROS / UDPROS | DDS（RMW 实现：FastDDS/CycloneDDS） |
| 生命周期 | 无 | Managed Node（configure/activate/...） |

> 迁移场景中若 rosbridge 或消息类型变化，必须写独立的**接口迁移说明**，不得直接覆盖旧协议（见 `interfaces/rosbridge/`）。
