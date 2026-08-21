# 最新上下文检查点
- updated: 2026-08-21 21:49 CST
- active_map: 用户已切换并确认 API 当前地图为 `dinggu7_6`；`dinggu7_6.pcd`（1,383,836,063 bytes）与 `dinggu7_6_display.pcd`（3,988,780 bytes）均可读，地图/DB 未修改。
- action: 调用现有 `GET /api/control/mode/navigation`，返回“已切换到导航模式”，`pcd_running=true`；现有 launch manager 自动启动 PCD publisher，无需手工启动/重启进程，也未重启 scout-nav 容器。
- publisher: 新进程 PID 1012，命令为 install/lib/nav_api/pcd_map_publisher.py，参数指向 dinggu7_6.pcd；日志确认加载 dinggu7_6_display.pcd、332,384 点并 latched 发布。
- verify: `/global_cloud_navigation` 收到 PointCloud2：frame_id=map、width=332384、data length=3,988,608；`rostopic hz` 为约 0.100–0.101 Hz；rosbridge_websocket 已订阅。
- note: ROS Master 仍显示旧不可通信节点 `/pcd_map_publisher_160_1787315341336` 的 stale registration，同时新健康节点为 `/pcd_map_publisher_1012_1787320124189`；未执行 rosnode cleanup，避免额外状态变更。

## 2026-08-21 PR1 测试准备检查
- 本地已具备 PR1 测试包：`F:\slamibot_agent\pr1-deploy.tar`、`pr1-overlay.tar`；SHA256 已记录于本次任务终端输出，未解包/部署。
- PR1 代码覆盖 `nav_multi/point_arrived`、到点拍照分发、任务执行与相关 FastAPI/前端点云文件；本地 `.venv-pr1-test` 可用（Python 3.13.12）。
- 当前仍不可进行真机/Jetson 测试：上一检查点确认需先完成“保留 DB/地图元数据 + nav_multi 源码/安装层对齐 + 启动导航模式”的授权部署；Jetson 当前按规则视为关机，未尝试 SSH。
- 测试入口准备：部署完成后先做只读节点/topic/API/rosbridge 冒烟，再做静止机器人 T1（任务创建/执行与状态）、T2（到点事件与拍照），最后才允许低速运动测试。
- tests: SKIPPED (read-only readiness check; no deployment or robot action)

## 2026-08-21 PR1 最小部署（22:09–22:12 CST）
- 用户明确授权 Jetson PR1 最小部署；LAN SSH `192.168.31.135` 成功，未执行大范围读取。
- 部署前确认：容器 `scout-nav:base-mode-ready-20260820`；源码与 DB 使用 `Scout_mini_navigation-pr1-test` 挂载；DB 有 Map=16、PointPosition=51、TaskFlow=14、TaskPoint=68，未覆盖地图/DB。
- 变更：仅将 `/Scout_mini_navigation/src/nav_api/scripts/nav_multi_node.py` 对齐复制到 `install/lib/nav_api/nav_multi_node.py`，随后仅重启 nav_multi 进程；源码/安装层 SHA256 均为 `dd3aab...c0c6aa8`，确认包含 `/nav_multi/point_arrived`。
- 运行：调用 `/api/control/mode/navigation` 成功；状态为 `current_mode=navigation`、`navigation_running=true`、`pcd_running=true`；地图 API 返回有效记录。
- 未执行：未重启 scout-nav 整体容器、未修改地图/数据库、未执行机器人运动。ROS topic 命令因远端 shell setup 引号问题未形成有效证据，需后续用容器内正确 bash 环境补查。
- tests: SKIPPED (deployment smoke only; robot motion not started)

## 2026-08-21 APP 默认动作补充
- 用户确认动作管理为空，需要默认动作方便点位选择；已委派 Claude Code 在 `F:\SLAMIBotApp` 做最小改动。
- 当前 diff：`NavigationModels.kt` 增加仅在后端动作列表为空时使用的内置模板 `photo`（拍照）与 `tts`（TTS播报）；`NativeNavigationController.kt` 在动作加载为空时回退到模板。
- 默认模板 `id=0`、仅前端展示，不写入后端；现有“添加动作”仍用于自定义动作。用户已有 APP 未提交改动保留，未运行构建。
- 注意：PR1 后端已确认 `photo` 到点分发；`tts` 是否有 Jetson 端执行器仍需单独确认，不能先宣称可用。
- tests: SKIPPED (user fast mode; no build)

## 2026-08-21 APP 新建点位默认拍照修复
- 已在 `F:\SLAMIBotApp\app\app\src\main\java\com\example\metacam\NativeNavigationPages.kt` 将 `PointEditorDialog` 新建点位的动作初值设为 `photo`。
- 编辑已有点位仍保留原 `point.action`（包括空值），不会覆盖旧数据；动作内容仍默认为空。
- 未构建/安装 APK；保留 APP 仓库原有用户改动。
- tests: SKIPPED (user fast mode; source diff checked only)

## 2026-08-21 容器重启后进程检查
- `scout-nav` 当前运行约 2 小时；API 状态为 navigation，`base_running/navigation_running/pcd_running=true`。
- 指定进程均存在，但 PID 已变化（容器 PID namespace 与用户提供的 PID 不同）：scout_base_node=231、map_server=1809、amcl=1810、move_base=1811、pcd_map_publisher=1837；均为运行态。
- rosbridge：内部 19090 为容器 PID 61/宿主 PID 36012；外部 9090 为宿主 PID 79679；两者均存在。
- `rosnode ping` 对 scout_base_node、map_server、amcl、move_base、pcd_map_publisher 成功；API 状态确认导航与 PCD 已运行。
- 关键 topic 检查至少确认 `/map`、`/global_cloud_navigation`、`/nav_multi/status`；本次不做进程重启或修复。
- tests: SKIPPED (read-only runtime check)
