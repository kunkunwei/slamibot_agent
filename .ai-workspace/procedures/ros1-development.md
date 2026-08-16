# 流程：ROS1 开发（ros1-development）

> 只适用于 ROS1（CURRENT）。严禁混用 ROS2 命令/launch/参数。

## 环境
- Ubuntu 20.04，ROS1 distro 待确认（预计 Noetic），build: catkin_make（或 catkin build）。
- 事实源：`facts/navigation_ros1_profile.yaml`。

## 常用命令（速查）
```
source /opt/ros/<distro>/setup.bash
source <catkin_ws>/devel/setup.bash
catkin_make                    # 构建
catkin_make run_tests          # 测试
roscore
roslaunch <pkg> <file>.launch
rostopic list / echo / pub
rosparam get / set
rosrun tf view_frames          # 查 TF
```

## 规则
- 改前 `git status`，改后 `git diff` + 摘要。
- 新依赖必须写进 `facts/navigation_ros1_profile.yaml` 的 `dependencies`。
- 任何 ROS1 → ROS2 迁移不在此流程，走 `ros1-to-ros2-migration.md`。
