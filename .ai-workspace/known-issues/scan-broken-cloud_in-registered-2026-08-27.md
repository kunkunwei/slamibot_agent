# /scan 断链根因：lidar_to_scan.launch 的 cloud_in 指向 /cloud_registered（FAST_LIO 话题）

- 状态: **已修复（容器内对齐原始代码）**（2026-08-27）
- 技术栈: ROS1 Noetic / AMCL + move_base / scout-nav 容器（install-only）/ 底盘轮式 odom
- 影响面: 导航模式下 /scan 无消息 → AMCL 无激光输入 → 定位不工作 → "2D 导航重定位不准"

## 现象
- `/scan` `no new messages`；`/amcl_pose` 无持续输出；`pointcloud_to_laserscan` 订阅 `/cloud_registered` 但该话题 `Publishers: None`。
- 用户反馈 2D 导航重定位不准；曾尝试 FAST_LIO 3D 重定位也有问题。

## 根因（已确认，2026-08-27 实测）
- 容器内 `lidar_to_scan.launch`（src + install 两份，字节一致）的 `pointcloud_to_laserscan` 被改成 `cloud_in:=/cloud_registered`。
- `/cloud_registered` 只有 FAST_LIO（laserMapping）发布，而**导航模式根本不启动 FAST_LIO**（launch_manager `start_navigation()` 只启动 my_nav_launch.launch）。→ 无发布者 → pointcloud_to_laserscan 无输入 → `/scan` 空 → AMCL 无激光 → 无定位。
- 原始代码（gitee / F:\slamibot_test / F:\d360_nav2D）该文件为 `cloud_in:=/livox_pcl0`（`livox_repub` 直接转发原始雷达点云，不依赖 FAST_LIO）。
- 拓扑事实：所有导航进程在 **scout-nav 容器内**，路径 `/Scout_mini_navigation`（宿主机无此路径）；`/livox/lidar` 由宿主机 `/root/SLAMIBOT_D360_Framework` 的 livox 驱动发布。

## 修复内容（容器内，已对齐原始代码）
- 文件：`/Scout_mini_navigation/src/my_nav/launch/lidar_to_scan.launch` + `install/share/my_nav/launch/lidar_to_scan.launch`
- 改动（共 3 处，与原始逐字节 diff 确认）：
  1. `cloud_in`：`/cloud_registered` → `/livox_pcl0`（**断链根因**）
  2. `max_height`：`1.0` → `0.5`
  3. 删除 FAST_LIO 残留的 `fastlio_body_to_base_link` static_transform_publisher（body→base_link）
- 替换后两份 md5 = `72cb13d0b468ab2de378ec0bf13575b2`（与原始 F:\slamibot_test 一致）。
- 备份：容器内 `*.bak-20260827-cloud_registered`（src + install 各一份）。
- 重启方式：pkill 容器内 `roslaunch my_nav`（lidar_to_scan + my_nav_launch）→ `GET /api/control/mode/navigation` 让 launch_manager 检测到进程已死并重新拉起。

## 已验证全链路（2026-08-27 实测）
- `/scan` 10Hz（frame=base_link，`cloud_in:=/livox_pcl0`）
- `/odom` 50Hz（/scout_base_node）
- `/livox_pcl0` 10Hz（frame=laser，19968 点，由 /livox_repub 转发）
- map_server 加载 map2701（1271×941 @ 0.05m，origin [-15.93,-22.60]）
- `map→odom` TF 由 /amcl 发布；`odom→base_link` 50Hz；`base_link→laser`（RSP）
- `/amcl_pose` 有校正输出（实测位置 x≈-0.45, y≈-2.51，非 initialpose 的 0,0）

## 决策（用户确认方案 A）
- AMCL `update_min_d=0.1 / update_min_a=0.15` **保持原始值**，不改 -1.0。
- 预期行为：导航移动中 AMCL 持续校正；**机器人静止时暂停更新、map→odom TF 间歇消失**（update_min_d 门槛），表现为"标哪停哪"。如需彻底解决静止也持续更新，需改 `update_min_d/a=-1.0`（known-issue `amcl-pose-publish-and-relocalization-2026-08-27.md` 已验证 0.0 无效、必须负数），本次不执行。

## 待用户 APP 验收
1. 手动标 initialpose → 观察箭头是否贴合地图特征。
2. 发导航目标 → 观察导航过程中位姿是否准确（移动中应被 scan 校正）。
3. 若静止标点后箭头不动，属方案 A 预期行为；确认是否需要后续改 -1.0。

## 持久化注意
- 本次修改在容器内文件系统；容器**重建**（docker rm + recreate）后会丢失。持久化需改 Dockerfile/挂载或同步到本地源（本地 F:\d360_nav2D 与原始本已一致，无需改动）。

## 关联
- `known-issues/amcl-pose-publish-and-relocalization-2026-08-27.md`（AMCL update_min_d 静止不更新）
- `known-issues/robot-state-publisher-exits-scan-broken-2026-08-26.md`（RSP 退出导致的另一种 /scan 断链，与本根因不同）
- `known-issues/fastlio-odometry-integration-2026-08-27.md`（3D 重定位方案现状）
