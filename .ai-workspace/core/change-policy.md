# 修改边界与变更策略（Change Policy）

每个项目必须明确四类范围（在 `projects/*/project.md` 中声明）：
- `allowed_paths`：任务可修改的文件/目录。
- `protected_paths`：默认禁止修改的路径。
- `protected_interfaces`：禁止改动的对外接口/协议。
- `protected_infrastructure`：禁止改动的基础设施。

## 默认禁止（除非任务明确授权）
- 系统环境（Ubuntu 包、环境变量、系统服务）
- Jetson OS 与系统配置
- Docker 基础设施（镜像、网络、compose 结构、daemon 配置）
- ROS 工作区结构（catkin_ws / colcon_ws 的目录约定）
- rosbridge 对外接口
- 数据库结构
- 前后端公共协议
- ROS1 / ROS2 版本迁移（必须 `migration: true` 专项任务）
- 用户已有未提交代码

## 变更边界铁律
- **不擅自扩大范围**：小任务不顺手重构；不“既然改了就一起改”。
- **越界即停**：发现改动会触碰 protected 范围时，停止并报告，请求扩权或新任务。
- **迁移绝不隐式触发**：普通 ROS1 Bug 修复 / 功能开发不得触发 `migration`。

## 技术栈生命周期（详见 system-lifecycle.md）
- 默认所有导航优化 / Bug 修复 / 功能开发以 **CURRENT（ROS1 + Ubuntu 20.04）** 为目标。
- 仅当任务显式 `migration: true` 且写清 `from` / `to` 时才进入 MIGRATION / TARGET。
