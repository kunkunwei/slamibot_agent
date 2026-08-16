# 项目：frontend（SLAMIBotApp）

> 前端控制/监控 APP，通过 rosbridge 与导航通信。应依赖接口定义，而非 ROS1/ROS2 内部实现。

## 基本信息
- id: frontend-app
- name: SLAMIBotApp
- repo: https://github.com/electech6/SLAMIBotApp.git
- local_path: UNKNOWN          # clone 后回填
- lifecycle: CURRENT（与 ROS1 基线配套）
- tech_stack: UNKNOWN          # Flutter / React Native / Native？clone 后确认

## 允许修改范围（allowed_paths）
- TODO：clone 后明确（页面、组件、状态管理等）

## 禁止修改范围 / 受保护接口
- rosbridge 对外接口（Topic/Service/消息格式/状态码/错误码）
- 后端公共协议
- 不得绕过接口直接依赖 ROS1/ROS2 内部实现

## 开发流程
- 遵循 `procedures/frontend-validation.md`
- 接口变更必须先改 `facts/rosbridge_profile.yaml` / `facts/frontend_api.yaml` 并评审，再改代码。

## 事实源
- `facts/frontend_api.yaml`
- `facts/rosbridge_profile.yaml`
