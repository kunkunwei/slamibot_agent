# 项目：frontend（SLAMIBotApp）

> 前端控制/监控 APP，通过 rosbridge 与导航通信。应依赖接口定义，而非 ROS1/ROS2 内部实现。

## 基本信息
- id: frontend-app
- name: SLAMIBotApp
- repo: https://github.com/electech6/SLAMIBotApp.git
- local_path: `F:\SLAMIBotApp`
- lifecycle: CURRENT（与 ROS1 基线配套）
- active_branch: `codex/native-compose-filament`
- tech_stack: Android / Kotlin / Jetpack Compose / Filament

## 允许修改范围（allowed_paths）
- 必须由具体任务进一步收窄；当前端口任务只授权
  `app/app/src/main/java/com/example/metacam/RobotEndpoint.kt`。

## 禁止修改范围 / 受保护接口
- rosbridge 对外接口（Topic/Service/消息格式/状态码/错误码）
- 后端公共协议
- 不得绕过接口直接依赖 ROS1/ROS2 内部实现
- 不得夹带工作树中已有的未跟踪文档和环境脚本

## 开发流程
- 遵循 `procedures/frontend-validation.md`
- 接口变更必须先改 `facts/rosbridge_profile.yaml` / `facts/frontend_api.yaml` 并评审，再改代码。

## 事实源
- `facts/frontend_api.yaml`
- `facts/rosbridge_profile.yaml`
