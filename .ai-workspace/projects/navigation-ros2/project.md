# 项目：navigation-ros2（Go2 机器狗 3D 导航，ROS2）

> 独立 ROS2 产品线（宇树 Go2 / Go2-W 机器狗 3D 导航），**非 Scout mini 的迁移结果**。
> 与 ROS1（Scout mini 2D）严格隔离。

## 基本信息
- id: navigation-ros2-go2-3d
- name: KN 导航工作区（3d_nav）
- repo: https://gitee.com/lion-king2025/3d_nav.git
- local_path: "F:\\3d_nav"
- lifecycle: 独立 ROS2 产品（非 CURRENT 迁移；若未来做 Scout mini 的 ROS1→ROS2 迁移，才走 migration 专项）
- tech_stack: { ros: ros2, distro: humble, ubuntu: "22.04", build: colcon }

## 规划链路
- 全局规划：PCT（pct_planner，3D，依赖 GTSAM）
- 局部规划：SCAN-Planner（默认）/ Pure Pursuit（测试链路）
- 定位：fast_lio + open3d_loc

## 允许修改范围（allowed_paths）
- TODO：按具体任务声明

## 禁止修改范围 / 受保护接口
- ROS1（Scout mini 2D）代码与工作区
- 管理接口：/switch_map、/restart_navigation（见 src/service.md）
- 状态 Topic 语义：/navigation_status、/localization_status、/current_map
- 底盘速度桥：/go2_cmd_vel_bridge

## 开发流程
- 遵循 `procedures/ros2-development.md`
- 接口权威来源：`src/service.md` + `src/web_api/API.md`（仓库自带）

## 事实源
- `facts/navigation_ros2_profile.yaml`
