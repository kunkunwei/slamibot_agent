# 流程：ROS2 开发（ros2-development）

> 只适用于 ROS2（TARGET / 独立 ROS2 任务）。严禁混用 ROS1 命令/launch/参数。
> 注意：普通 ROS1 任务不得切换到本流程；本流程不得触碰 ROS1 基线。

## 环境
- Ubuntu 22.04，ROS2 distro 待确认（预计 Humble），build: colcon，RMW 待确认。
- 事实源：`facts/navigation_ros2_profile.yaml`。

## 常用命令（速查）
```
source /opt/ros/<distro>/setup.bash
source <colcon_ws>/install/setup.bash
colcon build                   # 构建
colcon test                    # 测试
ros2 run <pkg> <node>
ros2 launch <pkg> <file>.launch.py
ros2 topic list / echo / pub
ros2 param get / set
ros2 run tf2_tools view_frames
```

## 规则
- Nav2 / DDS(RMW) / action 相关事实回填 `facts/navigation_ros2_profile.yaml`。
- 若属于 ROS1→ROS2 迁移，必须走 `ros1-to-ros2-migration.md` 专项授权。
