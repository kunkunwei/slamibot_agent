# 当前任务（current）

> 只记录尚未完全验收或仍需人工决策的任务。已完成操作及证据见 `completed.md`。

## TASK-2026-08-19-001：D360 前后端双 rosbridge 联调

- goal: APP/WEB 统一使用 9090，FastAPI/nav_api 内部保持使用 19090。
- project: frontend-app + navigation-ros1-d360 + deployment
- technology: ros1 + android + web + docker
- lifecycle: CURRENT
- migration: false
- status: in_progress
- authorized_scope:
  - `F:\SLAMIBotApp` 分支 `codex/native-compose-filament` 的默认 rosbridge 端口
  - Jetson `/home/jetson/Scout_mini_navigation/docker-entrypoint.sh`
  - Jetson `/home/jetson/Scout_mini_navigation/frontend/deploy/nginx.conf`
  - 指定 `scout-nav` 镜像/容器的构建、部署与验证
- forbidden:
  - 不修改摇杆代码或测试
  - 不修改 ROS Topic/Service/消息格式、导航算法、地图恢复内容或数据库结构
  - 不进行 ROS1→ROS2 迁移
- achieved:
  - Jetson 当前运行 `scout-nav:map2d-topic-copy-20260820`。
  - 9090 与 19090 同时监听，节点分别为 `/rosbridge_websocket`、`/scout_nav_rosbridge`。
  - Nginx `/rosbridge` 最终配置指向 `127.0.0.1:9090`。
  - FastAPI `/health` 返回 `rosbridgeConnected:true`。
  - APP `RobotEndpoint.DEFAULT_ROSBRIDGE_PORT` 已从 19090 改为 9090，已在提交 `3426f0a` 中提交并存在于远端 `codex/native-compose-filament` 分支。
- validation_history:
  - `RobotEndpointTest`: PASS
  - `assembleDebug`: PASS
  - 全量单测: 63/64；唯一失败是既有 G20 摇杆旧期望，与端口改动无关，未修改摇杆代码。
  - 2026-08-19 15:41 Jetson 只读复核: 80/5000/9090/19090 均监听，两个 rosbridge 节点均存在，`/health` 正常。
  - 2026-08-20 用户确认 WEB 与 APP 点位管理均已显示 2D 栅格地图；9090 `/map` CBOR 探针 PASS。
- remaining:
  - 地图与默认点云已通过 WEB/APP 人工验收；位姿和控制的完整端到端联调仍待执行。
  - 已在热点 `192.168.117.6` 与公司 Wi-Fi `192.168.31.135` 下完成 APP 实测。
  - 用户反馈：热点模式下进行导航时容易出现卡顿，但等待一段时间后可自行恢复；暂未形成稳定复现和根因结论。
  - 当前网络已从热点切换为公司 Wi-Fi，目标地址为 `192.168.31.135`。
- rollback:
  - APP：只回退 `RobotEndpoint.kt` 的单行端口修改。
  - Jetson：历史 scout-nav 容器/镜像已按用户授权删除；如需回退，基于远端分支 `codex/fix-initial-map-cloud` 的提交重新构建，不得依赖已删除容器。

## TASK-2026-08-19-004：地图清理遗留项人工决策

- goal: 决定 `test_map` 的关联数据如何处理，并复核 `office_room_test` 数据库记录是否应恢复。
- project: navigation-ros1-d360
- technology: ros1 + sqlite
- lifecycle: CURRENT
- status: needs_confirmation
- current_scope: READ_ONLY
- facts:
  - `test_map` 没有可用 2D 文件，数据库仍有 8 个点位、5 个任务、12 个任务点，未删除。
  - 已完成：删除 `test_map` 记录，并级联删除 8 个点位、5 个任务、12 个任务点。
  - 原备份已按用户要求删除；当前不保留本次 `test_map` 删除专用备份。
  - 验证：删除前后 `PRAGMA integrity_check` 均为 `ok`；删除后目标地图、点位、任务、任务点计数均为 0。
  - `office_room_test` 的数据库记录已删除，但同名 YAML+PGM 文件仍存在；可从清理前备份恢复该记录。
- forbidden:
  - 未经明确授权不得级联删除点位、任务、任务点。
  - 不得删除或覆盖地图恢复文件。
- validation:
  - 决策后再次执行 SQLite `PRAGMA integrity_check`，并核对 WEB `/app/points` 列表。
- rollback: 使用 `nav_api.db.pre-map-cleanup-20260819_141713.bak`，禁止直接覆盖当前库；应先停写并做新的当前库备份。







'

## TASK-2026-08-20-008：更换 BOX 后重新连接和测试 R1 麦克风

- status: in_progress
- scope: R1 麦克风设备识别、udev 绑定核对、音频输入和语音交互最小测试
- topology: R1 麦克风阵列搭载于 BOX；BOX 通过网线和 USB 连接 D360；D360 含 Jetson、雷达、RTK、相机、网卡和电源模块
- current_state: 当前 BOX 暂不作为项目阻塞项，已有其它 BOX 可替换；本次日志显示串口 `/dev/lg_speech_serial` 可打开并完成握手，但 ALSA 未找到 `ListenGo` 音频设备，语音识别启动失败。
- expected_devices: `ListenGo Circular 6-Microphone` (`2208:0001`)；`QinHeng USB` (`1a86:7523`)
- expected_paths: `/dev/lg_speech_uac`、`/dev/lg_speech_serial`
- source: 用户提供《R1麦克风阵列模块大模型语音交互功能部署》资料
- safety: 先只读检查 `lsusb`、udev 规则、设备节点、ALSA 和网络状态；不猜测重复设备的 `devpath`，不写入 API 凭证
- new_issue: APP 到 BOX 的喊话和回传链路可能打断语音识别；当前仅有现象和启动日志，根因待定位
'



## TASK-2026-08-20-009：2D 静态地图临时障碍“空气墙”

- project: navigation-ros1-d360
- technology: ros1 + move_base + costmap_2d
- lifecycle: CURRENT
- migration: false
- status: diagnosed
- current_scope: READ_ONLY
- symptom: 建图期间存在的临时障碍被写入二维静态地图；实物移走后，全局规划仍将该区域视为占据栅格。
- root_cause: 地图保存流程将 FAST_LIO 累积 PCD 投影为 PGM；导航的 `global_costmap/static_map: true` 加载该 PGM。`/scan` 虽启用 `marking` 与 `clearing`，但清除只作用于实时障碍层，不能擦除静态地图占据单元。
- preferred_solution: 静态地图只保留墙体、固定设施等结构；桌椅、纸箱、车辆等可移动物体交给实时 obstacle layer 标记和射线清除。
- immediate_options: 清场重建地图，或对确认区域离线修补 PGM/源 PCD 后生成新地图版本并人工验收。
- advanced_option: 若必须自动消除静态残影，新增保守的可变覆盖层，基于多帧、多视角自由空间证据及可编辑区域白名单覆盖静态占据；不得直接无条件清除静态层。
- validation: 对比 `/map`、`/move_base/global_costmap/costmap`、`/move_base/local_costmap/costmap` 与 `/scan`，确认残影首先存在于 `/map`。
- forbidden: 未授权不修改地图文件、costmap 参数、ROS 接口或 Jetson 运行环境。

## TASK-2026-08-20-010：导航点位与任务接口产品化审计

- project: navigation-ros1-d360 + frontend-app + deployment
- technology: ros1 + FastAPI + SQLite + Docker
- lifecycle: CURRENT
- migration: false
- status: assessed
- current_scope: READ_ONLY
- available_interfaces:
  - 点位 CRUD、排序、按当前 AMCL 位姿踩点：`/api/map/point/*`
  - 单点导航：`POST /api/map/nav_custom`，支持数据库点位和临时 map 坐标
  - 多点任务 CRUD/执行/暂停/恢复/取消/状态：`/api/map/task/*`、`/api/map/nav_multi/*`
  - ROS1 内部：`move_base` action、`/nav_multi/execute|pause|resume|cancel`、`/nav_multi/status`
  - FastAPI 自动 OpenAPI `/docs`、`/openapi.json`，并注册同源 MCP tools
- container_facts: 一体化镜像包含 Web、FastAPI、内部 rosbridge 和 nav_multi；地图与 SQLite 数据库已有宿主机卷挂载方案。
- product_gaps:
  - 无鉴权、TLS、RBAC、API 版本路径和幂等请求机制。
  - 导航执行未校验点位/任务所属地图是否为当前激活地图。
  - HTTP `next/end/passage` 只有预留包装，当前 ROS nav_multi 节点未注册对应 service。
  - APP 仍存在 `/api/map/nav_multi` 与后端 `/api/map/nav_multi/execute` 的路径契约差异。
  - `action/actionContent` 已入库，但未在 nav_multi 到点后执行。
  - 导航状态为进程内状态，容器重启后不恢复任务。
  - SQLite 仅执行建表 schema，尚无正式迁移/version 管理。
- recommendation: 面向客户冻结 `/api/v1` 北向 API；ROS/rosbridge 作为容器内部实现；外部仅经 80/443 网关访问，并为地图、点位和任务增加 revision、鉴权、审计、幂等和持久化状态。
- forbidden: 未授权不修改接口、数据库 schema、APP、镜像或 Jetson。
