# 流程：导航调试（navigation-debug）

面向：Planner 超时、TF 异常、代价地图、定位、rosbridge 异常等导航问题。

## 步骤
1. **确认栈**：先判断 ROS1 还是 ROS2（读 package.xml / 环境 / launch）。禁止混淆。
2. **采集事实（READ_ONLY）**：
   - ROS1：`rosnode list` / `rostopic list` / `rostopic echo <t>` / `rosparam get ...` / `rosrun tf view_frames`
   - ROS2：`ros2 node list` / `ros2 topic list` / `ros2 topic echo <t>` / `ros2 param get ...` / `ros2 run tf2_tools view_frames`
3. **核对事实源**：与 `facts/navigation_ros1_profile.yaml`（或 ros2）对照，发现不符即修正事实源。
4. **定位（Explorer）**：形成假设并标注；不确定处写 `NEEDS_CONFIRMATION`。
5. **修改（Implementer）**：仅限导航相关 scope。
6. **验证（Validator）**：build → 仿真 → 真机（授权时）。

## 常见问题入口
- Planner 超时 / TF 问题 / rosbridge 异常 / Docker 网络问题 / Jetson 特定问题 → 先查 `known-issues/`，未记录则新增。
