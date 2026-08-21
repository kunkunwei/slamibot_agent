# 项目：backend（FastAPI 后端）

## 基本信息
- id: backend
- name: nav_api FastAPI 后端
- repo: 内嵌于 `d360_nav2D`
- local_path: `F:\d360_nav2D\src\nav_api`
- lifecycle: CURRENT（与 ROS1 导航基线配套）
- tech_stack: Python 3.11 / FastAPI / Uvicorn / SQLite / rosbridge

## 允许修改范围（allowed_paths）
- 默认仅 `F:\d360_nav2D\src\nav_api`，具体任务继续收窄到目标文件。

## 禁止修改范围 / 受保护接口
- 未经任务授权不得修改 `src/nav_api` 之外的导航代码。
- 数据库结构、前后端公共协议、rosbridge Topic/Service/消息字段和 Docker 基础设施默认受保护。

## 开发流程
- 接口不变时直接实施，不重复审查稳定接口。
- 接口变化时先更新 `facts/backend_api.yaml` 和相关前端/rosbridge 事实源。
- 与导航 lane 并发时路径必须不重叠，必要时使用独立 Git worktree。
- 完成后走轻量 diff、开发分支上传，然后直接进入用户手动现象/抓包驱动的联调。

## 事实源
- `facts/backend_api.yaml`
- `facts/rosbridge_profile.yaml`
