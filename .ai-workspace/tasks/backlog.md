# 待办任务（backlog）

> 尚未开始或排队中的任务。格式同 `current.md`。

## 建议的首批真实任务（待人工确认后启动）
- id: TASK-NEXT-001
  goal: clone D360 导航仓库并回填 facts/navigation_ros1_profile.yaml
  project: navigation-ros1
  technology: ros1
  ubuntu: "20.04"
  lifecycle: CURRENT
  scope: [新增 clone + 回填事实源，只读分析仓库]
  forbidden: [不修改导航业务代码, 不触发 migration]
  validation: [facts 回填完成且字段来源可追溯]
  status: backlog
  notes: 需先确认本机 clone 位置；clone 后由 Explorer 只读分析。

- id: TASK-NEXT-002
  goal: clone SLAMIBotApp 前端仓库并回填 facts/frontend_api.yaml 与 rosbridge_profile.yaml
  project: frontend
  technology: app
  lifecycle: CURRENT
  scope: [新增 clone + 回填事实源]
  forbidden: [不修改前端业务代码]
  validation: [事实源回填完成]
  status: backlog

- id: TASK-NEXT-003
  goal: 连接 Jetson，只读分析板内代码（含外协 3D 导航），补充事实源
  project: workspace
  technology: mixed
  lifecycle: CURRENT
  scope: [只读查看 Jetson 文件/容器/ROS 环境，回填 facts/ 与 repos.yaml]
  forbidden: [不修改 Jetson 任何代码/环境/容器]
  validation: [外协 3D 导航与自研 3d_nav 事实源补充完成]
  status: backlog
  notes: 用户上班后连板子；默认 READ_ONLY 权限。

<!-- 在此追加新任务 -->
