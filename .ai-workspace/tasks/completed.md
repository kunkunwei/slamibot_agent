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

## TASK-2026-08-27-004A：Jetson MJPEG 后端部署

- status: completed（2026-08-27）
- scope: `scout-nav-timefix-20260827` 的 FastAPI `app.py`/`capture.py`；未编译、未构建镜像、未删除或重建容器。
- result: 新增 `GET /api/camera/stream.mjpeg`，同步宿主 src、容器 src 与 install；保留全部现场后端补全、自愈和导航修复。
- backup: `/home/jetson/slamibot-backups/mjpeg-20260827-160108`。
- validation: D360 重启后 health/launch/base_mode 200；MJPEG 4 秒 32 帧且 JPEG 边界完整；局域网可访问；拍照 POST 200；容器稳定且 RestartCount=0。
- tests: Jetson runtime smoke PASS；build/compile SKIPPED（用户要求只复制）。
## TASK-2026-08-27-004B：导航 MJPEG 视频与拍照真机验收

- status: completed（2026-08-27，用户真机确认）
- result: APP 导航控制页实时视频与拍照功能均正常；视频地址为 `/api/camera/stream.mjpeg`。
- source: ROS1 `/SLB_CAM_B/compressed` 经 FastAPI 最新帧缓存转换为 HTTP MJPEG，不是 RTSP。
- follow_up: 功能验收完成；约 22–23 Mbps 的 MJPEG 带宽及摇杆延迟作为独立优化项保留在 known issue。
- validation: USER_DEVICE_VALIDATED；本次仅同步工作台日志，未修改 Jetson/ROS/Docker 运行态。

## TASK-2026-08-27-005：近期工作周会报告整理

- status: completed
- scope: 仅本地文档 `docs/weekly-report-2026-08-27.md` 与工作台任务记录；未修改业务代码或运行环境。
- result: 将容器、ROS、APP、导航、音视频和售后工作去重整理为周报，并附约 3 分钟口头汇报稿。
- accuracy: 区分已确认事实、部分解决项和待验证推测；未将孤儿进程/TCP 端口机制写成已证实唯一根因。
- validation: Markdown 文本检查完成；tests: SKIPPED（文档任务）。
- safety: 未连接 Jetson，未操作 Docker/ROS，未提交或推送 Git。

## TASK-2026-08-27-006：Claude Code MCP 失败自动降级到 Luna

- status: completed
- scope: 本地工作台编排规则与交接文档；未修改 MCP Server、业务代码或运行环境。
- result: Claude Code MCP 未注册/连接失败/CLI、认证、Provider、网络、限流、无响应或超时时，自动由 `gpt-5.6-luna` 以 `reasoning_effort: low` 按原委派 scope 单次接管。
- guardrails: 不绕过用户或权限拒绝、scope/cwd/参数错误、危险操作确认、protected 边界或普通实现/测试失败；MCP 失败不取消 Sol 门禁。
- reporting: 降级结果统一标记 `fallback: claude-code MCP -> gpt-5.6-luna (low)`，并记录原始失败类别与 Codex 独立验证。
- validation: 规则文件一致性与任务范围 diff 检查；tests: SKIPPED (documentation/policy only)。
- safety: 未连接 Jetson，未修改 ROS、Docker、Git 历史或 MCP JavaScript 实现。

## TASK-2026-08-28-002：Sol 主代理与 Luna 执行子代理配置

- status: completed
- scope: Kimi Code 用户配置与本地工作台模型路由规则；未修改业务代码或 MCP Server。
- main_agent: `custom/gpt-5.6-sol`，effective effort `high`，负责需求理解、方向控制、风险/接口裁决和最终验收。
- secondary_agent: 默认 `custom/gpt-5.6-luna`，effective effort `low`；模型池同时保留 Sol 供确有价值的独立专家分析。
- runtime: 已配置 `[secondary_model]`，并永久设置 Windows 用户环境变量 `KIMI_CODE_EXPERIMENTAL_SECONDARY_MODEL=1`；新 Kimi 进程生效。
- routing: 1–2 次简单调用由 Sol 直接完成；超过约 3 次搜索/读取、长文件/长日志或独立并行扫描优先委派 Luna。
- validation: 候选和正式配置均通过 `kimi doctor`；结构差异仅为 Luna effort 与 `secondary_model`；工作台规则一致性、任务范围 diff 与 `git diff --check` 均 PASS。
- backup: `C:\Users\kun\.kimi-code\config.toml.20260828-125627.bak`。
- tests: SKIPPED (configuration/policy only)；未连接 Jetson，未修改 ROS、Docker 或 Git 历史。

## TASK-2026-08-30-001：Codex Windows 沙箱读取器 ACL 修复

- status: completed
- symptom: `exec_command` 与 Node REPL 均在进程启动前失败，错误为 `helper_unknown_error: setup refresh had errors`。
- root_cause: `F:\my_story\.agents` 被 `CodexSandboxOffline` 持有；沙箱 setup refresh 无权写入保护性 deny ACE，日志报 `SetNamedSecurityInfoW ... error 5`。
- fix: 无删除移动原目录至 `.ai-workspace/backups/sandbox-acl-20260830-my_story-agents/original.agents`，再复制回原路径以恢复正常所有权。
- integrity: `.agents` 共 13 个文件，修复前后及备份 SHA-256 全量一致；用户已有 Git 修改保持不变。
- validation: 沙箱内 PowerShell PASS；Node REPL 工作台读取 PASS；后续 setup refresh 多次 `errors=[]`，`setup_error.json` 已清除。
- safety: 未连接 Jetson，未修改 ROS/Docker/业务文件内容/Git 历史或远端；保留原目录与 ACL/哈希清单用于回滚。
- tests: PASS（执行器与 Node REPL 定向运行验证）。

## TASK-2026-08-31-001：2D 导航两个容器与本机/Jetson 源码版本核对

- status: completed（只读盘点）
- current_runtime: `scout-nav-timefix-20260827` / `scout-nav:jetson0826-src-timefix-20260827` / image `d6ca5df6...`；完整包含 src+install，Uvicorn 从 install 加载。
- installonly: 停止容器 `scout-nav` / `scout-nav:0cf1d78-installonly-lf-20260826` / image `43316a6994...`；原生 install-only，约 542 MB 可写层含兼容 src、GMapping、launch 资源和 live patch。
- source_versions: 本机当前 `codex/2026_8_25@a467ff8`；本地 `codex/scout-nav-recovery-20260826` 也被移动到 `a467ff8`；Jetson `jetson/0826@00aa4b1`，工作树另有 204 D、17 M、19 未跟踪。
- gitee_refs_live: 2026-08-31 `git ls-remote` 确认 `codex/2026_8_25@a467ff8`，`codex/scout-nav-recovery-20260826@73b84bb`；本地 recovery ref 不可替代远端事实。
- commit_relation: `0cf1d78 -> ... -> 73b84bb (引入 3D 重定位) -> 80dc2ea (修复 3D launch) -> a467ff8 (assistant/capture 等后端同步)`。
- source_vs_image: 上述三个 Git 提交的主 Dockerfile 都 COPY src+install；停止的 `0cf1d78-installonly` 是实际镜像/现场构建属性，不能用提交内主 Dockerfile直接复现或解释。
- runtime_result: 当前 `/scan`、`/amcl_pose` 有消息；`/cloud_registered`、`/Odometry` 不存在；无 3D 重定位进程，当前走标准 2D AMCL 链路。
- drift: 多个后端/launch 文件在 Jetson host src、host install、当前容器 src/install、旧容器 install 之间哈希不一致；禁止直接以任一目录整体覆盖其它目录。
- safety: 仅 SSH/Docker/ROS/Git 只读命令；未修改 Jetson、容器、ROS 参数、业务仓库或 Git 历史。
- tests: SKIPPED（只读盘点；仅做运行态消息存在性检查）。

## TASK-2026-09-01-002：ROS1 产品 install-only 镜像构建与离线验收

- status: completed（构建与离线验收完成；部署另行安排）
- source: `codex/product-nav-runtime-refactor-20260831@ec245a7`；Jetson 独立构建仓库 detached clean，同提交。
- image: `scout-nav:product-ec245a7-c411cf9d-arm64` / `sha256:c411cf9d926b67a783e0892b4e7d783c4f655723da9a88372438ce6fbef726b9` / arm64 / 5,279,683,353 bytes。
- result: Docker BuildKit 构建 PASS；runtime 仅含 install，无 src/build/devel；关键 ROS 包、Python API、持久化默认路径及 PCD 非破坏守卫均通过离线验证。
- safety: 未停止或替换 `scout-nav-timefix-20260827`，未改 compose，未连接硬件 ROS，未 prune、未删除地图/旧镜像/缓存，未部署产品镜像。
- tests: PASS（完整 arm64 image build、无网络临时容器 smoke、`verify_install_runtime.py`）；真机导航回归待部署窗口。
- publish: 产品分支尚未推送 Gitee。

## TASK-2026-09-01-USB-CAMERA-BANDWIDTH：旧板相机 USB 链路带宽估算
- status: completed（只读分析）
- result: 依据单路 compressed 实测约 0.35 MB/帧，估算三路 5/10/20 FPS 有效负载约 44/88.5/177 Mbps；底层 USB 若传未压缩数据可升至 Gbps 量级。
- conclusion: 现有证据不能把断连唯一归因于带宽；历史 SuperSpeed 后 reset、Bootloader 480M、X_LINK_ERROR 和约 100°C 高温同时指向线材/信号、供电、拓扑、温度或设备稳定性。
- next: 开机后只读确认 USB 枚举速率与拓扑，并同步采集 USB/内核日志及 ROS topic 带宽。
- safety: 未连接 Jetson，未修改业务代码、ROS、Docker 或运行态；tests: SKIPPED。

## TASK-2026-09-01-LEARNING-ROADMAP：AI 辅助机器人开发能力转化建议
- status: completed（方法与学习路线输出）
- result: 形成以真实 SLAMIBot 故障为教材的学习顺序、每日闭环、AI 使用协议和阶段验收标准；不要求停止使用 AI。
- safety: 未连接 Jetson，未修改业务代码、ROS、Docker 或运行态；tests: SKIPPED。

## TASK-2026-09-01-FREE-LEARNING-RESOURCES：免费系统学习资料筛选
- status: completed（截至 2026-09-01 在线核验）
- result: 按 Linux/OS/网络、编程与构建、ROS1、ROS2、Jetson、Docker、机器人与 SLAM 分类筛选官方或高校免费资源，并给出学习优先级。
- note: ROS1 Noetic 文档用于当前既有系统维护；ROS2 新板按 Humble 版本文档学习，禁止混用命令和配置。
- safety: 未连接 Jetson，未修改业务代码或运行态；tests: SKIPPED。

## TASK-2026-09-01-LEARNING-DOCS：Linux / Jetson / ROS 学习资料库

- status: completed
- output: 在 `F:\Linux_Learning` 创建 7 份 Markdown：总索引、六个月路线、免费网站导航、首月执行计划、AI辅助学习与复盘、SLAMIBot故障到知识点索引、检索与记录模板。
- content: 覆盖 Linux/OS/网络、Git/Python/C++/CMake、Docker、ROS1 Noetic、ROS2 Humble、Jetson、定位/导航/SLAM，并把近期真实故障映射到知识点和证据化排查路径。
- safety: 仅创建学习文档；保留目标目录原有 `shell_test`；未连接 Jetson，未修改业务代码、ROS/Docker运行态或Git历史。
- validation: 7 个文件存在，Markdown代码围栏成对，README相对链接全部可解析。
- tests: SKIPPED（纯 Markdown 文档任务）。

## TASK-2026-09-03-711-LED：711 D360 LED 不亮维修

- status: completed（用户现场验收）
- device: 711 D360 / ROS1 Noetic；IPv6 网线 SSH `fe80::4ebb:47ff:fe51:6a41%15`，独立别名 `d360-711-eth1`。
- symptom: LED 不亮；`/led_control` 在线，但 `/system_monitor` 已退出，`/stm32_serial` 缺失，`/stm32_cmd` 无订阅者。
- root_cause: 日志确认 `/dev/ttySTM32` 曾瞬断并报 `Errno 19 No such device`，SystemMonitor 因串口错误退出且未 respawn，启动 LED 命令丢失。
- hardware: 两路 CH341 已枚举；本机型 `/dev/ttySTM32 -> /dev/ttyUSB0`，连续检查稳定；不得套用 704 的 ttyUSB1 映射。
- recovery: `project_duration=0.0` 后，经用户授权仅重启 `core`；SystemMonitor、STM32 ROS 话题和 GPRMC 回传恢复。
- led_validation: 用户授权单次低亮红灯测试并确认亮起；随后恢复系统常亮蓝灯，用户确认正常。
- safety: 未重启 `firmware-sensors`、未刷固件、未改配置、未直接打开串口；每次远端写操作均单独取得授权。
- residual: USB 再次瞬断时 SystemMonitor 仍可能退出；未实施自动 respawn 或 USB 根因修复。系统时间 1970 未在本任务处理。
- validation: PASS（ROS 节点/话题、STM32 回传和物理 LED 现场验收）。

## TASK-2026-09-03-711-LED-GUARD：711 STM32/LED 事件驱动自恢复

- status: completed（故障注入与用户现场验收）
- design: 新增 `/stm32_cmd_latch_relay`，仅订阅稀疏 `std_msgs/String /stm32_cmd`，以 `queue_size=1` latched 发布 `/stm32_cmd_guarded`；无 timer、轮询、sleep、shell、大 topic 或持续磁盘写入。
- recovery: `/system_monitor` 设置 `respawn=true`、`respawn_delay=5` 并订阅 guarded topic；只重启故障节点。LEDControl 原样运行，未增加启动延迟。
- persistence: `/etc/slamibot/system/overrides/{core.launch,stm32_cmd_latch_relay.py}` 只读 bind mount；compose 仅增加这两个 core mount。
- backup: `/home/jetson/slamibot-backups/711-stm32-guard-19700101-081105/`。
- static_validation: Python py_compile、launch XML、`docker compose config` PASS；本地 staging 为 `.ai-workspace/tmp/d360-711-stm32-guard/`。
- runtime_validation: relay 约 40 MB RSS；节点只连接两个 String topic。单次 `rosnode kill /system_monitor` 后约10秒自动 respawn，core 与 firmware-sensors 的 ID/StartedAt 在注入前后不变，缓存灯态自动重放。
- recovery_side_effect: 部署时重建 core 导致 ROS Master 更换，未重启的传感器进程未重新注册；经用户额外授权单次重启 firmware-sensors 后恢复 Livox 9.7Hz、keyframe 2.9Hz、driver_status=3。
- field_validation: 用户最终确认 LED 蓝灯正常。
- residual: 最后一次 SSH 读取被对端 reset，随后 TCP 22 超时且 Windows 邻居显示 711 IPv6 Unreachable；已停止重试。设备现场仍开机、网线正常、蓝灯正常。
- safety: 未刷固件、未直接打开串口、未读取图像/点云正文、未增加现有操作延迟；respawn_delay 仅是故障节点的5秒防抖。
- fallback: claude-code MCP -> gpt-5.6-luna (low)；failure category: MCP 未注册/未暴露；主代理独立核验通过。

## TASK-2026-09-03-WEEKLY-REPORT：截至9月3日工作周报

- status: completed
- output: `.ai-workspace/tasks/weekly-report-2026-09-03.md`。
- scope: 重新核对工作台 facts/current/completed/checkpoint，整理 2026-08-31 至 2026-09-03 的 ROS1 产品化与导航、704恢复、D360S ROS2、711售后、语音及前后端功能进展；按用户要求不纳入个人学习资料、USB相机带宽分析及已终止的APP/WEB导航轨迹诊断。
- quality: 明确区分已验证、仅诊断、待真机验收和硬件阻塞；附问题风险表、下周P0/P1/P2计划和周会口述版。
- validation: 文件存在；工作内容、风险表、下周计划和口述版完整，Markdown结构检查PASS。
- safety: 未连接Jetson，未修改业务代码、ROS/Docker运行态或Git历史。
- tests: SKIPPED（纯Markdown周报）。

## TASK-2026-09-04-NAV-AI-WORKSPACE-GUIDE：导航同事本地 AI 工作台生成指南

- status: completed
- output: `.ai-workspace/procedures/navigation-ai-workspace-generation-guide-2026-09-04.md`。
- content: 提炼当前工作台的独立 Git 架构、核心规则、事实源、项目边界、任务流程、Agent 角色、Git/远端权限、ROS1/ROS2 隔离、MVP 与验收清单，并提供可复制模板。
- privacy: 未复制现场 IP、账号、凭据、设备标识、镜像/容器、客户数据、历史任务或临时热修材料。
- delegation: Luna 子代理启动失败，failure category: 503 No available providers；主代理按相同只读范围接管。
- safety: 未连接 Jetson，未修改业务代码、ROS/Docker 运行态、接口或 Git 历史。
- tests: SKIPPED（纯 Markdown 文档）；Markdown 围栏、标题结构和任务范围 diff 检查 PASS。

## 2026-09-04 Scout 产品数据持久化迁移

- 将现有地图、PCD、SQLite、相册与TTS缓存无损迁移到宿主 `/var/lib/slamibot/scout-nav`；采用同盘rename，未复制21G数据、未删除原数据。
- 镜像内18组旧2D地图无覆盖补入宿主；25条DB地图均有有效YAML，活动`map0901`的PCD/YAML存在。
- 4组仅PCD数据隔离到`maps/pcd-only`；历史隔离地图与DB备份进入独立archive。
- SQLite integrity=ok；Map=25、PointPosition=11、TaskFlow=4、Captures=16；16张相册均存在且HTTP抽样200；TTS=11。
- 新容器运行正常，restart=unless-stopped、health=200、RestartCount=0、OOM=false；旧容器与首次空启动容器均停止保留。
- 首次脚本遗漏`docker run -i`导致空数据启动；及时停止，原数据未动；空启动数据和容器均作为审计证据保留，v2修正后完成迁移。

## TASK-2026-09-04-D360-704：恢复已验证轻量v3守护并清理备份

- status: completed；用户现场确认当前热点/WiFi与传感器功能可正常使用。
- runtime: 保持`core`、`firmware-sensors`、`ota_web`三容器和原command；`/use_sim_time`未设置，无LED relay。
- known_good: 恢复轻量v3 `/usr/local/sbin/d360-{auto-recover,quick-recover,clear-stale-clients}`，`d360-auto-recover.timer`为`enabled/active`；rosbridge心跳为5秒、超时10秒。
- persistence: 正式心跳launch迁移到`/etc/slamibot/system/overrides/rosbridge-heartbeat-core.launch`，Compose仅增加该文件的只读mount。
- cleanup: 删除本次产生的factory/ROS-time/LED-guard/known-good/旧heartbeat备份目录及四个失败启动实验文件；保留正式守护脚本、systemd units、Compose、MID360配置和固件。约释放1.0MB。
- safety: 清理过程未重启容器，三个容器PID/StartedAt保持不变；`docker compose config`通过。
- fallback: claude-code MCP -> gpt-5.6-luna (low)；failure category: MCP未注册/未暴露；主代理完成状态核对。

## TASK-2026-09-04-711-GUARD-ROLLBACK：撤销 STM32/LED 守护实验

- status: completed；用户现场确认711实体LED与基本使用状态正常。
- rollback: compose恢复原哈希`71be6a37...`；core与firmware-sensors重建/重启后均运行原镜像`sha256:44594f...`、restart=always。
- runtime: 原始core.launch=`bafda818...`、sensors.launch=`fecac8a8...`；无relay进程/节点、无override mount、无guard配置。
- audit: `/etc/slamibot/system/overrides/`与本地`.ai-workspace/tmp/d360-711-stm32-guard/`仅保留未挂载审计文件，不参与运行。
- app_lag: 设备端A/B、热点/公司WiFi、701对照后用户确认问题来自新版APP；按用户要求停止继续排查，不修改711设备端。
- safety: 未刷固件、未删除备份、未修改镜像或业务代码；最终状态为原始可用版本。

## TASK-2026-09-04-NAV-PARAM-SYNC：同步同事实测导航参数

- status: completed；仅同步当前运行态已实际生效的 TEB 到点容差 0.25/0.30。
- source: Jetson `scout-nav-product-9eebfd5-persistent-20260904` rosparam + 宿主 dirty 文件交叉核对。
- rejected: 未生效的 camera_init、扩大 Livox 自滤波框、max_height=1.0、额外静态TF，避免破坏当前 TF/scan 基线。
- commit: `a2b232e`；已推送 `kunkunwei/codex/product-f376a4c-release-20260903`。
- runtime: 未重启、未部署、未修改地图/数据库/相册或其他 AI 模块。
- tests: SKIPPED（仅参数源码同步）；静态差异与字段检查 PASS。
- fallback: claude-code MCP -> gpt-5.6-luna (low)；Sol 独立验收。

## 2026-09-04 产品导航参数固化与主线统一
- status: **completed / pushed**
- product: `codex/product-nav-runtime-refactor-20260831@140f049`，已同步Jetson现场5项有效导航参数并双推。
- master: GitHub/Gitee均更新到`698be43`；非force push；其文件树与产品提交完全一致。
- safety: 当前产品分支未合入旧master内容；地图、artifacts、pycache保持未提交。
- tests: XML PASS；diff-check PASS；build/deploy SKIPPED（本轮仅参数固化与Git主线统一）。

## TASK-2026-09-04-APP-POINTCLOUD-PERF：APP 点云性能修复与 v1.6.6 发布

- status: **completed / released**；用户真机确认开始采集、强度点云和流畅度正常。
- app: `v1.6.6`；版本提交/标签 `a1be671`；远端 `main` 后续 CI 修复提交 `b0e7dc2`。
- changes: Lidar RGB 默认关闭；强度伪彩恢复；累计500k、单帧100k、native均匀抽点、2个staging buffer、点云10Hz、ACCUMULATE约30FPS。
- release: GitHub Actions `33890348247` SUCCESS；Release `SLAMIBot v1.6.6` 已发布；资产 `slamibot_v1.6.6.apk`（31,338,464 bytes）。
- ci: 内部服务器上传增加连接/总超时、重试及非阻断策略；手动发布可更新既有版本 Release。
- validation: 用户真机 PASS；CI Release APK 构建/Artifact/Release PASS；本地 Gradle 因 Windows AGP/NDK NPE 未完成。
- safety: 非 force push；未移动 `v1.6.6` 标签；独立 release worktree 保留；业务仓库其它改动未夹带。
- fallback: claude-code MCP 未暴露，按规则由 `gpt-5.6-luna (low)` 完成 CI 单文件修改；Sol 独立检查 diff、提交、发布与 Release 资产。
- tests: device PASS；CI build PASS；local Gradle BLOCKED (environment)。

## TASK-2026-09-05-OAK-SINGLE-NODE-RUNBOOK：OAK 相机节点快速恢复文档

- status: completed；用户按单节点启动方案操作后确认相机恢复出图。
- diagnosis: A/B/C 无 Publisher；`/oak_hardware_trigger_ros` ping connection refused；容器内无真实驱动进程；Livox 与 timeshare 仍持续更新。
- recovery: 在 `firmware-sensors` 内按原 launch 参数单独启动 `ros1_oak_ffc_sync/oak_hardware_trigger_ros`；无需重启存活的 `/oak_keyframe_stitcher`。
- time_model: ROS1 使用 `/use_sim_time=true`，`/clock` 为 ROS 时间权威；Jetson 系统墙钟/互联网 NTP 与该恢复判定隔离，不作为门槛。
- docs: 新增 `.ai-workspace/procedures/oak-camera-node-quick-recovery-2026-09-05.md`；更新客户恢复手册、ROS1 Docker 相机假死 known issue、ROS1 时间事实及两份 704 历史文档的 NTP 更正。
- validation: 文档命令与本地 `sensors.launch` 参数交叉核对；现场 A/B/C 出图、`git diff --check` PASS；提交 `a7edb5d`；push 因目的地授权安全策略未完成；tests SKIPPED (user fast mode)。
- fallback: claude-code MCP -> gpt-5.6-luna (low)；failure category: MCP 未注册/未暴露；Sol 主代理独立检查任务范围差异。

## TASK-2026-09-05-JETSON-PRODUCT-BUILD-F281B8E：唯一构建仓库与产品容器切换
- status: **completed / built / deployed / static-runtime-pass**。
- source: 本地/GitHub/Jetson `codex/video-link-stream-20260904@f281b8e`；仅5个shell脚本LF规范化，未推Gitee。
- build_repo: 固定 `/home/jetson/scout-nav-product-build`；中断clone原地修复，未再创建仓库；工作树干净。
- workflow_guard: 禁止另建/另克隆/复制构建仓库，禁止从电脑上传源码包；Jetson只从既有GitHub远端在固定仓库`fetch`并`ff-only`更新。不得新增远端、推送Gitee、force push或上传无关代码，除非用户当次明确授权。
- image: `scout-nav:product-v1-f281b8e-arm64`，ID `31df59f2...03e60e97ff`，Jetson原生ARM64构建PASS。
- runtime: `scout-nav-product-v1-f281b8e-test-20260905`，health/rosbridge PASS，restart=unless-stopped，RestartCount=0，OOM=false。
- persistence: 唯一挂载 `/var/lib/slamibot/scout-nav:/var/lib/slamibot/scout-nav`；DB/maps/PCD可见。
- params: 新源码、新镜像与此前健康运行容器的6个导航参数SHA256完全一致。
- rollback: 旧 `dc05f79` 容器停止保留；firmware-sensors及ROS时间链未触碰。
- tests: image smoke PASS；post-switch health/runtime/persistence PASS；现场导航与建图验收PENDING。
## TASK-2026-09-05-JETSON-OBSOLETE-SOURCE-CLEANUP：清理历史上传源码副本
- status: **completed / verified**。
- deleted: `/home/jetson/product-build/d360_nav2D-2b0bc9c`、`product_builds/scout-nav-9eebfd5`、`scout-nav-build-d0b7b15{,-lf}`、`scout-nav-build-dc05f79-20260905`，以及2个源码tar包和对应旧构建脚本/日志；父目录仅在空目录时以`rmdir`移除。
- protected: `/home/jetson/scout-nav-product-build@f281b8e`、`/home/jetson/Scout_mini_navigation@00aa4b1`、`/var/lib/slamibot/scout-nav`均存在且未改；未删除Docker镜像或容器。
- runtime: `scout-nav-product-v1-f281b8e-test-20260905`继续运行，镜像`scout-nav:product-v1-f281b8e-arm64`。
- disk: 本次约释放12GB，最终根盘为`171G used / 50G free / 78%`。
- workflow_guard: 后续不得上传源码副本或另建仓库；只允许固定仓库从既有GitHub远端`fetch`并`ff-only`更新。
- validation: 每个目标逐项不存在；两个保护仓库HEAD、运行容器及磁盘状态复核PASS。

## TASK-2026-09-05-D360S-WEB-SOURCE：纠正 D360S 5001 页面来源

- status: **completed / runtime_pass / pushed**。
- source: 从Gitee main对象`29242022982652045f142e550fccfc989add15a7`恢复完整`ota_server/web_page/**`；根`web_page/static/main.js`恢复到SCAN基线`2a2dc1b`。
- routing: `ota_server/setting_server.py`默认仅使用`ota_server/web_page/{templates,static}`；可由`SLAMIBOT_WEB_ROOT`覆盖，缺文件启动明确失败，绝不回退根SCAN页面。
- adaptation: D360页面使用ROS2 `pkg/msg/Type`、`pkg/srv/Type`，`/project_control=project_control/srv/Base`，预览订阅`/SLB_CAM_A/compressed`；页面HTML/JS移除云台、扫拍、PRY、gimbal、survey及RTK控件/调用，保留WiFi网络扫描。
- runtime: systemcontrol+rosbridge+OTA三前台受控启动；GET `/`与`/static/main.js`均200，JS SHA与源码一致；rosbridge真实CAM_A JPEG、`driver_status=9`、`get_version=0.1.0`；Chrome headless加载PASS。
- shutdown: 5001/9090关闭、相关进程none、两锁free、三服务disabled/inactive、STM32 `STATE=READY`。
- git: `fa6d22567f33102115a7b423dce3c73f1adbcfd7`，提交`fix(web): restore D360 device console`，已普通push并以`ls-remote`核对。
- evidence: Jetson `/home/jetson/d360s-system-backups/web-fix-20260905-214103`与`web-fix-runtime-20260905-215621`。
