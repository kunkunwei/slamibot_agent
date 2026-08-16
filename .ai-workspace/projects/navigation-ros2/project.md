# 项目：navigation-ros2（未来目标，TARGET）

> 未来目标架构。仅允许在明确迁移设计/开发任务中修改；禁止普通 ROS1 任务触碰本栈。

## 基本信息
- id: navigation-ros2
- name: 导航（ROS2）
- repo: UNKNOWN
- local_path: UNKNOWN
- lifecycle: TARGET
- tech_stack: { ros: ros2, ubuntu: "22.04", distro: UNKNOWN, build: colcon, rmw: UNKNOWN }

## 允许修改范围（allowed_paths）
- TODO：仓库落地后明确

## 禁止修改范围
- 现有 ROS1 导航代码与 ROS1 工作区（CURRENT 基线，迁移需专项授权）
- 系统环境 / Docker 基础设施 / rosbridge 接口

## 受保护接口
- rosbridge 契约；ROS1 对外接口

## 开发流程
- 遵循 `procedures/ros2-development.md`
- 迁移遵循 `procedures/ros1-to-ros2-migration.md`（`migration: true`，需人工批准）

## 事实源
- `facts/navigation_ros2_profile.yaml`
