# 项目：navigation-ros1（D360 导航，CURRENT）

> 稳定基线，默认保护对象。任何普通优化/Bug 修复/功能开发默认以本栈为目标。

## 基本信息
- id: navigation-ros1-d360
- name: D360 导航（ROS1）
- repo: https://gitee.com/electech6/d360_nav2D.git
- local_path: `F:\d360_nav2D`（本机只读参考）；Jetson 实施路径 `/home/jetson/Scout_mini_navigation`
- lifecycle: CURRENT
- tech_stack: { ros: ros1, ubuntu: "20.04", distro: noetic, build: "catkin_make install" }

## 允许修改范围（allowed_paths）
- 无全局默认写权限；每个任务必须明确到具体文件。
- Jetson 默认 READ_ONLY；构建、部署和删除分别需要任务授权。

## 禁止修改范围（protected_paths / protected_infrastructure）
- 任何 ros2/ 相关目录与代码
- docker/ 基础设施（镜像/网络/compose 结构）
- rosbridge 对外接口（见 `facts/rosbridge_profile.yaml`）
- 前后端公共协议
- 用户已有未提交代码

## 受保护接口（protected_interfaces）
- rosbridge Topic/Service/消息格式/状态码 —— 默认禁止改动
- 前后端约定的导航/任务状态与错误码

## 开发流程
- 遵循 `procedures/ros1-development.md`
- 验证：build → 单元测试 → 导航仿真 → 真机（Jetson，仅授权 DEPLOY 时）
- 技术栈隔离：见 `core/tech-stack-isolation.md`，严禁混用 ROS2 命令/launch/参数。

## 事实源
- `facts/navigation_ros1_profile.yaml`
- `facts/robot_profile.yaml`
