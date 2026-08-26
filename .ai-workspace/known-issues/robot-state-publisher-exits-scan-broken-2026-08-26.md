# robot_state_publisher 未运行导致 /scan 断链、导航与 3D 定位全断

- 状态: **open（待重启导航栈验证）**（2026-08-26）
- 技术栈: ROS1 Noetic / Ubuntu 20.04 / Jetson Orin NX / Docker scout-nav（宿主机跑 roslaunch，容器/宿主机共享 master 127.0.0.1:11311）
- 影响面: 导航无反应（AMCL 无定位、costmap 无障碍）、APP 3D 点云箭头不更新、/scan 无消息

## 现象
- `rostopic hz /scan` → `subscribed to [/scan]` / `no new messages`
- `rostopic hz /amcl_pose` → 同（无消息）
- `rostopic info /robot_map_pose` → `Publishers: None`（更早为 `Unknown topic`）
- `ps -ef | grep robot_state` → **无进程**

## 根因（已确认）
- `my_nav_launch.launch` → include `lidar_to_scan.launch` → include `scout_mini_robot_base.launch` 中无条件启动的 `robot_state_publisher`（`scout_mini_robot_base.launch:59`）**未存活**。
- robot_state_publisher 负责发布 `laser→base_link`（URDF `laser_joint`，fixed）的 TF；它不在运行 → laser frame 不在 TF 树。
- `pointcloud_to_laserscan`（`target_frame=base_link`，`transform_tolerance=0.01`）无法对 `/livox_pcl0`（frame_id=`laser`，10Hz 正常）做 transform → 无 `/scan` 输出。
- 雷达原始链路本身正常：`/livox/lidar` 10Hz、`/livox_pcl0` 10Hz 均正常。**不是雷达/点云断，是 TF 断。**
- 历史 roslaunch 日志曾见 RSP 启动后 ~0.3s `finished cleanly` 退出，疑似启动时机早于 URDF 参数加载/解析。

## 已确认的关键事实
- 参数服务器 `/robot_description` **完整**（11.5KB），含 `laser_joint`（type=fixed，parent=`base_link` → child=`laser`）→ **RSP 只要存活就会发布 laser→base_link TF**。
- 板上 URDF 来自 `install/share/scout_description/urdf/scout_mini.urdf.xacro`。

## 解决/规避
- **方案 A（首选，待用户重启验证）**：重启导航栈 `my_nav_launch.launch`（launch_manager 管理），让 RSP 重新拉起。参数已就位，RSP 应能存活并发布 TF，/scan→AMCL→/robot_map_pose 全链路恢复。
- **方案 B（若 A 后 RSP 仍秒退）**：改 launch 启动顺序，确保 URDF 参数先加载再起 RSP，或给 RSP 加参数就绪等待。**属业务代码修改，须先与用户确认再动。**

## 验证命令（重启后跑）
```bash
# 板上（宿主机, 需 source /opt/ros/noetic/setup.bash）
rostopic hz /scan          # 期望有频率（约 3.3Hz 或更高）
rostopic hz /amcl_pose     # 期望有消息
rostopic info /robot_map_pose   # 期望 Publishers 非空（rosbridge 转发）
tf_echo base_link laser    # 期望有 static TF
```

## 关键坑
- costmap inflation 参数查法：带 `inflation_layer/` 前缀，`rosparam get /move_base/global_costmap/inflation_layer/inflation_radius`；无前缀会报 `not set`（易误判）。
- costmap_2d 无 dynamic_reconfigure 接口，膨胀参数改后**必须重启 move_base 生效**。
- 容器 `nav-api-entrypoint` 是 bash 脚本，`wait $API_PID` 结尾，无 supervisord → **不能只 kill uvicorn（容器会退出），只能 `docker restart scout-nav`**。

## 关联
- `known-issues/robot-map-pose-no-publisher-2026-08-26.md`（3D 箭头转发）
- 膨胀 0.10 同步见任务 `TASK-2026-08-26-001`
