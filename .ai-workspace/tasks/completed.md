# 已完成任务（completed）

> 完成任务后从 `current.md` 移入此处，并保留关键结论与证据。

## 历史
- id: TASK-2026-08-16-000（示例，验证工作流）—— 完成。无业务修改。
- id: TASK-NEXT-001 —— 本机 `F:\d360_nav2D` 已接入并回填 ROS1 导航事实源。
- id: TASK-NEXT-002 —— 本机 `F:\SLAMIBotApp` 已切到 `codex/native-compose-filament` 并回填前端/rosbridge 事实源。
- id: TASK-NEXT-003 —— 已通过只读 SSH 盘点 Jetson；持续事实见 `facts/jetson_profile.yaml` 与知识库。

## TASK-2026-08-19-002：清理没有可用 2D 地图的前端地图记录（第一轮）

- status: completed_with_follow_up
- authorized_by_user: 2026-08-19，要求删除 `/home/jetson/Scout_mini_navigation/src/my_nav/maps/` 中没有 2D 地图、却显示在前端的地图。
- database: `/home/jetson/Scout_mini_navigation/src/nav_api/db/nav_api.db`
- pre_operation_backup: `/home/jetson/Scout_mini_navigation/src/nav_api/db/nav_api.db.pre-map-cleanup-20260819_141713.bak`
- backup_size: 65536 bytes
- file_quarantine: `/home/jetson/Scout_mini_navigation/src/my_nav/maps/.quarantine/maps-without-2d-20260819_141713/`
- database_deleted_rows:
  - `Map.id=7 office_room_test`：记录未声明 `yamlFilePath`；同名 YAML+PGM 实际仍存在，因此只删了数据库记录，未删文件。
  - `Map.id=8 office_room_test123`：记录指向的目录内基础 YAML/PGM 不存在；其它同名前缀变体不等于记录指向文件。
  - `Map.id=9 office_room_test3`：记录指向的基础 YAML/PGM 不存在；目录中只保留 `_map` 变体。
  - `Map.id=26 测试1`：无 `yamlFilePath`、无点位/任务/区域。
  - `Map.id=27 测试2`：无 `yamlFilePath`、无点位/任务/区域。
- filesystem_operations:
  - 未永久删除 `测试1`、`测试2` 的 PCD；两个目录被移动到隔离区。
  - 隔离区包含 `测试1/测试1.pcd`、`测试1/测试1_display.pcd`、`测试2/测试2.pcd`。
  - `office_room_test` 的 YAML+PGM 被保留。
- database_side_effects:
  - 活跃地图从 `cs1` 切换为 `slam_map`：`cs1.isActive 1 -> 0`，`slam_map.isActive 0 -> 1`。
  - 清理前后 `PointPosition`、`TaskFlow`、`TaskPoint`、`Area`、`CycleConfig` 均无增删改。
- intentionally_not_deleted:
  - `test_map`：虽无可用 2D 文件，但关联 8 个点位、5 个任务、12 个任务点；为避免未经确认的级联数据删除而保留。
  - `cs1`：数据库路径对应的 YAML+PGM 存在，保留记录和文件。
- verification:
  - 清理前备份 `PRAGMA integrity_check`: ok
  - 当前数据库 `PRAGMA integrity_check`: ok
  - 2026-08-19 只读复核确认五条 Map 记录已删除，关联表未变化，隔离文件与备份均存在。
- rollback:
  - 优先按需从备份中恢复指定 `Map` 行，或从隔离区恢复 PCD 目录。
  - 不得在 FastAPI 写库期间直接用备份覆盖当前数据库；恢复前先停写并备份当前库。


## TASK-2026-08-19-005：恢复 WEB/APP 2D 栅格地图

- status: completed
- accepted_by_user: 2026-08-20，用户确认 WEB 和 APP 均已显示 2D 栅格地图。
- root_cause:
  - idle 状态没有 `/map` Publisher；进入 navigation 后由 `/map_server` 发布占据栅格。
  - WEB 实际订阅 `/map`，但两处提示文案仍错误写成 `/plane_OccMap`。
  - APP CBOR 解析器和 core 9090 rosbridge live patch在本次复核时均正常，不是本次回归根因。
- deployed:
  - 当前容器：`scout-nav`
  - 当前镜像：`scout-nav:map2d-topic-copy-20260820`
  - 镜像 ID：`sha256:b28bd225b06b56ac9b7e4fdb77bad4331dfc1d8311e9cf5de14b46811911fa80`
  - 模式：navigation
- source_published:
  - 远端：Gitee `origin/codex/fix-initial-map-cloud`
  - `e2e71bc fix: publish active map cloud on initial load`
  - `3244e75 fix(web): correct 2D map topic hint`
  - `6912fde fix(deploy): persist dual rosbridge routing`
- verification:
  - WEB/APP 人工验收：PASS
  - FastAPI `/health`: PASS，`rosbridgeConnected:true`
  - 端口 80/5000/9090/19090：LISTEN
  - `/map` Publisher：`/map_server`
  - 清理后地图首帧：`1157x1071`、分辨率约 `0.05`；APP 同路径 `cbor-raw` 探针 PASS。
  - WEB 活跃入口引用 `PointsPage-BsOVElyc.js`，其中 `/map` 提示 PASS。
- cleanup:
  - 按用户 2026-08-20 明确授权，删除 3 个停止的历史 scout-nav 容器。
  - 删除旧标签：`initial-map-cloud-20260819`、`dual-rosbridge-20260819`、`latest`、`pre-dual-rosbridge-20260819`、`test`、`rollback-20260813-1132`。
  - 未执行 `docker prune`，未删除当前镜像，未操作 core/firmware/ota 等其他容器。
- remaining_risk:
  - core 9090 的三处 rosbridge CBOR 兼容 patch 仍是容器内 live patch，重建 core 后可能丢失；本任务未重建或删除 core。
  - idle 是否也必须显示当前地图仍是独立产品决策。

## TASK-2026-08-20-006：Luna 默认路由与小任务上下文压缩

- status: completed
- scope: 本地 AI 工作区与 Codex 全局模型配置；未修改业务代码。
- result:
  - 默认主模型切换为 `gpt-5.6-luna`，reasoning 为 `low`；Sol 仅按条件单轮升级。
  - 新增 `.ai-workspace/core/context-compaction.md` 和 `.ai-workspace/tasks/context-checkpoint.md`。
  - 规定每个小任务结束后覆盖短检查点，并按状态同步 `current.md` / `completed.md`。
- validation:
  - 全局配置仅模型和 reasoning 两行发生变化；工作区路由无旧 Sol 主协调冲突。
  - 业务测试：SKIPPED（user fast mode）。
- rollback:
  - 全局配置备份：`C:\Users\kun\.codex\config.toml.pre-luna-20260820`。

## TASK-2026-08-20-007：删除 test_map 及关联数据

- status: completed
- authorized_by_user: 2026-08-20，明确授权删除 `test_map` 及其关联数据。
- database: `/home/jetson/Scout_mini_navigation/src/nav_api/db/nav_api.db`
- backup: `/home/jetson/Scout_mini_navigation/src/nav_api/db/nav_api.db.pre-test-map-delete-20260820_093336.bak`（已按用户要求删除）
- deleted:
  - `Map.mapName=test_map`: 1 条
  - `PointPosition.mapName=test_map`: 8 条（id 1、2、4、5、6、7、65、66）
  - `TaskFlow.mapName=test_map`: 5 条（id 1-5）
  - `TaskPoint`：12 条（id 1-12，关联 taskId 1-5）
- verification:
  - 删除前 `PRAGMA integrity_check`: `ok`
  - 删除后 `PRAGMA integrity_check`: `ok`
  - 删除后目标地图、点位、任务、任务点查询结果均为 0
- note: `office_room_test` 记录恢复仍是独立待决事项。


## 2026-08-21：底盘自动/手动控制模式切换与 APP 状态显示
- Jetson 后端支持自动导航/手动遥控切换，手动模式接管 `/cmd_vel`，导航模式恢复自动控制。
- APP 导航控制→操控增加底盘模式显示与切换，保留触屏/G20/手柄输入和速度设置。
- 修复 `SCOUT` 底盘类型与控制权混淆：结合 `control`、`teleopEnabled`、中文 `modeLabel` 解析为自动/手动/未知。
- 摇杆实际链路已现场确认可控制小车。
- APP 编译、安装和真机部署按用户约定由用户手动执行。

## TASK-2026-08-21-003：复杂联调自动触发 Sol

- status: completed
- scope: 本地 AI 工作区模型路由文档；未修改业务代码或远端系统。
- result:
  - 前后端、后端导航等相互依赖的跨 lane 联调改为强制自动调用 Sol。
  - Luna 先收集最小事实，并在形成根因或实施方案前调用 Sol，不再等待用户点名或 Luna 失败。
  - 多 lane 但完全独立、无共享接口和共同故障现象时仍使用 Luna。
- validation: AGENTS、model-routing、team-orchestration、handoff 规则一致；业务测试 SKIPPED（user fast mode）。

## 本次恢复结论（2026-08-21）
- 3D 点云不显示的直接原因是激活地图 `dinggu7_5` 缺少 PCD 与 display PCD 文件，publisher 仅留下 stale ROS 注册。
- 切换到具有完整点云资源的 `dinggu7_6` 后，通过既有导航接口恢复 publisher，`/global_cloud_navigation` 正常发布，用户确认 3D 点云恢复。
- 未覆盖容器、未修改地图/数据库、未重启整个 scout-nav；底盘模式和手动控制未被破坏。
- 经验：恢复任务必须先以云端仓库为代码基线，再用最小命令核对实际挂载、激活地图资源和 publisher 状态，避免无关的容器级操作与重复读取。

## TASK-2026-08-24-001：APP/WEB 2D 地图缺失最小只读诊断路径
- status: completed（方案输出；待 Jetson 开机后人工采证）
- scope: 本地事实源、ROS1/双 rosbridge/Nginx/APP/WEB 契约只读分析；未连接 Jetson，未修改业务仓库。
- result: 形成 `/map` 发布 → scout-nav/19090 → core 9090 → Nginx 80 → APP/WEB 订阅的优先命令与结果分支；共享故障先查 `/map`，不先猜客户端。
- tests: SKIPPED (user explicitly prohibited remote operations)。
## TASK-2026-08-19-004：地图清理遗留项人工决策

- status: completed
- completed_at: 2026-08-24（用户确认）
- result: `test_map` 及其关联点位、任务和任务点已完成清理；用户确认本遗留决策任务结束，不再作为当前任务。
- safety: 本次仅同步工作台任务状态，未连接 Jetson，未修改地图、数据库或业务代码。
- tests: SKIPPED (workspace status sync only)
## TASK-2026-08-25-002：D360 图传网络下手动遥控延迟快速定位与优化
- status: completed
- completed_at: 2026-08-25（用户真机验收确认）
- result:
  - 实验A确认`/global_cloud_navigation`点云大流是图传手动遥控延迟主因；关闭点云后控制链路RTT与Send-Q显著下降。
  - APP正式实现图传`192.168.144.87:9090`默认关闭点云网络订阅，Wi-Fi/非图传默认开启；Dashboard开关可真实connect/disconnect，开关操作可逆。
  - 用户已测试图传模式和点云开关，确认功能正常，正式优化通过真机验收。
  - 保持`/map`订阅和`/cmd_vel_web` 25Hz不变；未修改Jetson、ROS、Docker或发布端。
- app_commit: `b808a9fcb6466c4b482fd9b9ba3e2e2c74494659`（已推送`origin/codex/native-compose-filament`）
- validation: USER_DEVICE_VALIDATED；本次仅同步工作台状态，未重新构建、测试、ADB或SSH。

## TASK-2026-08-27-003：移除 APP 导航摇杆上方控制模式标签

- status: completed
- scope: 仅 `F:\SLAMIBotApp\app\app\src\main\java\com\example\metacam\NativeNavigationScreen.kt`。
- result: 删除导航 Dashboard 左下角摇杆上方“当前控制：自动导航/手动遥控”独立显示标签。
- preserved: 摇杆启用条件、自动/手动切换逻辑、侧边控制设置与状态显示均保留。
- app_commit: `a6caadc`，已推送 `origin/codex/native-compose-filament`。
- validation: `git diff --check` PASS；tests: SKIPPED (user fast mode)。
- safety: 未连接 Jetson，未修改 ROS1、Docker、rosbridge 或 Git 历史。
