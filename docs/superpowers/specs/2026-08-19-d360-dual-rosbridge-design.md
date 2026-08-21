# D360 双 rosbridge 分工设计

- 日期：2026-08-19
- 状态：架构已批准；Jetson 部署已核验，APP 改动未提交，端到端联调未全部完成
- 适用系统：D360 CURRENT（ROS1 Noetic，Ubuntu 20.04）
- 不属于 ROS1 → ROS2 迁移任务

> 2026-08-19 实施更新：Jetson 双 rosbridge 与 Nginx 路由已通过端口、ROS 节点和
> `/health` 核验；APP 默认端口的一行修改仍未提交。当前状态见
> `.ai-workspace/tasks/current.md`，不能把本设计视为全部验收完成。

## 1. 背景

D360 当前在同一个宿主机 ROS Master（`127.0.0.1:11311`）上运行两套
`rosbridge_websocket`：

- `core` 提供客户端兼容端口 `9090`；
- `scout-nav` 计划为导航后端提供端口 `19090`。

两套进程当前都使用默认 ROS 节点名 `/rosbridge_websocket`。`scout-nav` 重启时，
容器内进程先监听 19090，随后因节点重名收到 ROS Master 的 shutdown 请求并退出。
Nginx、FastAPI 和容器主进程仍存活，因此容器显示 `Up`，但 `/health` 返回
`rosbridgeConnected:false`，WEB 与 Android APP 均无法建立正常的 ROS 通道。

Android 源码也存在配置分裂：README、架构文档、界面提示和单元测试均约定 9090，
但 `RobotEndpoint.DEFAULT_ROSBRIDGE_PORT` 后来被单独改为 19090，因此运行时实际连接
19090。浏览器 WEB 使用同源路径 `/rosbridge`，当前 Nginx 将其反代到 19090。

## 2. 已确认的运行事实

2026-08-19 在 Jetson 上只读核验：

- `core`、`firmware-sensors`、`scout-nav` 均在运行；
- 80、5000、9090 正在监听，19090 未监听；
- 9090 对应宿主机节点 `/rosbridge_websocket`；
- `scout-nav` 日志明确记录 `new node registered with same name`，随后关闭 19090；
- FastAPI `/health` 可访问，但 `rosbridgeConnected=false`；
- 从 `scout-nav` 容器使用真实 rosbridge 客户端连接 9090 成功，可看到雷达、IMU、
  三路 OAK 相机 Topic；导航 Topic 当时未注册，因为导航模式未运行；
- 两套容器使用 host 网络并共享同一个 ROS Master，Topic/Service 空间相同。

## 3. 目标

1. Android APP 与浏览器 WEB 统一使用客户端兼容 rosbridge 9090。
2. `scout-nav` 内部 FastAPI/nav_api 保持使用独立 rosbridge 19090。
3. 两套 rosbridge 使用不同 ROS 节点名；`core` 先启动后，重复重启 `scout-nav`
   不再导致任一 rosbridge 因重名退出。
4. 启动检查必须能发现“主进程还在、端口已关闭”的假成功。
5. 不改变 ROS Topic、Service、消息格式、FastAPI 接口和前端业务语义。
6. 在 Jetson 上完成 WEB、APP、FastAPI 与关键导航数据的端到端验证。

## 4. 非目标

- 不解决 9090/19090 的历史来源，也不合并为单一 rosbridge。
- 不增加 9090 与 19090 之间的客户端自动回退。
- 不修改 ROS1 导航算法、地图、数据库、传感器驱动、Docker 网络或 ROS Master。
- 不触碰当前正在恢复和暂存的地图文件及用户已有后端 API 修改。
- 不进行 ROS1 → ROS2 迁移。

## 5. 目标架构

```text
Android APP ────────────────────────┐
                                    ├──> core rosbridge :9090
浏览器 WEB ──> Nginx /rosbridge ────┘    node=/rosbridge_websocket
                                                   │
                                                   ▼
                                         ROS Master :11311
                                                   ▲
                                                   │
FastAPI/nav_api ──> 127.0.0.1:19090 ──> scout-nav rosbridge
                                         node=/scout_nav_rosbridge
```

### 5.1 端口与职责契约

| 端口/路径 | 使用方 | 提供方 | 职责 |
|---|---|---|---|
| `ws://<Jetson>:9090` | Android APP 全部 ROS 功能 | `core` | 客户端兼容 ROS 通道 |
| `ws(s)://<Jetson>/rosbridge` | 浏览器 WEB | Nginx → 9090 | 与 APP 等价的客户端 ROS 通道 |
| `ws://127.0.0.1:19090` | FastAPI/nav_api | `scout-nav` | 导航后端内部 ROS 通道 |
| `http://<Jetson>:5000` | APP/WEB | FastAPI | 非实时业务 API、健康检查 |
| `http://<Jetson>/app/` | 浏览器 | Nginx | WEB 静态资源和同源入口 |

两套 rosbridge 连接同一个 ROS Master，因此能够访问同一组 Topic 与 Service。端口分工
用于隔离客户端兼容通道和导航后端内部依赖，不用于隔离 ROS 数据域。

## 6. 组件改动

### 6.1 Android APP

权威开发分支为 `codex/native-compose-filament`，实施目录为用户重新克隆的
`F:\SLAMIBotApp`。2026-08-19 核验结果如下：

- 该目录是正常 Git 工作树，分支为 `codex/native-compose-filament`；
- HEAD 为 `f919874`，与 `origin/codex/native-compose-filament` 一致；
- 工作树干净；
- 旧目录 `F:\SLAMIBotApp_codex` 的 `.git` 仍指向已失效的 worktree，因此只作为只读快照
  保留；
- 排除 `.git` 后，新克隆目录与旧快照的 135 个文件内容一致；仅
  `scripts/android-env.sh` 与 `scripts/setup-android-env.sh` 的换行格式不同，不属于业务
  代码差异，无需迁移。

因此只在 `F:\SLAMIBotApp` 上实施和提交端口修改；不原地修复、覆盖或删除旧快照，也
不再创建额外的 `F:\SLAMIBotApp_codex_repo` 克隆。

修改：

- `app/app/src/main/java/com/example/metacam/RobotEndpoint.kt`
  - `DEFAULT_ROSBRIDGE_PORT` 从 19090 恢复为 9090。
- 保持 `DEFAULT_HOST=192.168.117.6`；这是 Jetson 热点地址，不是错误配置。
- `NativeControlSession`、导航地图、点云、位姿、采集和 RTK 均继续从同一个
  `RobotEndpoint.rosbridgeUrl` 派生，不增加第二个客户端端口或回退逻辑。
- 现有 `RobotEndpointTest` 对 9090 的期望应恢复通过；补充测试保证用户输入 URL 中的
  端口仍按既有规则丢弃并统一落到客户端默认端口 9090。

### 6.2 浏览器 WEB / Nginx

修改导航仓库：

- `frontend/deploy/nginx.conf`
  - `/rosbridge` 的 `proxy_pass` 从 `http://127.0.0.1:19090` 改为
    `http://127.0.0.1:9090`。

已部署 WEB 的 JavaScript 默认使用 `ws://${location.host}/rosbridge`，因此无须在前端
产物中硬编码 9090，也无须改变页面代码。HTTP/HTTPS 下分别自然使用 `ws`/`wss`。

### 6.3 导航 rosbridge / FastAPI

修改导航仓库：

- `docker-entrypoint.sh`
  - 19090 rosbridge 增加唯一 ROS 节点名 `__name:=scout_nav_rosbridge`；
  - 保留 `_port:=19090` 与板上现有 `_use_compression:=true`；
  - 启动验收同时检查 rosbridge 进程和 TCP 19090，不能只执行 `kill -0`；
  - 验收失败时打印 `/tmp/rosbridge.log` 并让容器启动失败，避免假健康。
- 保持 `ROSBRIDGE_HOST=127.0.0.1`、`ROSBRIDGE_PORT=19090` 不变。
- FastAPI `/health` 中的 `rosbridgeConnected` 继续代表导航内部 19090 的状态，不代表
  Android APP 到 9090 的连接状态。

宿主机 `core` 的 9090 rosbridge 和节点名 `/rosbridge_websocket` 均不修改。

### 6.4 事实源与操作文档

实施验证完成后更新：

- `.ai-workspace/facts/rosbridge_profile.yaml`；
- `.ai-workspace/facts/frontend_api.yaml`；
- `.ai-workspace/knowledge/d360-board-running-services.md`；
- `F:\d360_nav2D\快速操作手册.md` 中端口检查和故障恢复说明。

文档必须明确区分“客户端 9090”和“导航内部 19090”，不能再使用含混的“前端端口”或
“导航端口”而不说明调用方。

## 7. 启动、错误处理与可观测性

推荐启动顺序保持：

1. `core`：ROS Master + `/rosbridge_websocket` :9090；
2. `firmware-sensors`；
3. `scout-nav`：`/scout_nav_rosbridge` :19090 + Nginx + FastAPI；
4. 导航模式进程。

`scout-nav` 重启不得影响 9090。`core` 重启会重建 ROS Master，依赖方需要重新注册；
验收必须覆盖 `core` 先启动、`scout-nav` 后启动以及仅重启 `scout-nav` 两种场景。

诊断口径：

- APP/WEB 连接失败：先检查 9090、Nginx `/rosbridge` 和 `/rosbridge_websocket`；
- FastAPI `rosbridgeConnected=false`：检查 19090、`/scout_nav_rosbridge` 和
  `/tmp/rosbridge.log`；
- 端口正常但无地图/点云：检查对应导航 Topic 是否真正发布，不把模式未启动误判为
  rosbridge 故障。

## 8. 部署安全

Jetson `/home/jetson/Scout_mini_navigation` 当前包含大量恢复后已暂存地图，以及用户已有
未提交的 nav_api 修改。实施必须遵守：

1. 改前记录 `git status -sb` 和两个 Jetson 目标文件的 diff；
2. 只修改 `docker-entrypoint.sh` 与 `frontend/deploy/nginx.conf`，不暂存或提交地图、数据库
   和 nav_api 工作树修改；
3. 构建前确认恢复任务已停止，且 Docker 构建上下文不会重新删除或覆盖恢复文件；
4. 保留当前 `scout-nav:latest` 的可回滚镜像标签；
5. 重建容器时保持现有 host 网络、权限和地图/数据库 bind mount；
6. 禁止 `git reset --hard`、`git clean`、强制 checkout、批量删除和历史改写。

APP 侧保留当前断链代码快照，只在 `F:\SLAMIBotApp` 正常分支工作树修改并单独提交，
不夹带其它文件；未经确认不得删除或替换 `F:\SLAMIBotApp_codex`。

## 9. 验证策略

### 9.1 静态与单元验证

- APP：运行 `RobotEndpointTest` 及相关 Android 单元测试，确认实际 URL 为
  `ws://<host>:9090`。
- APP：确认 `F:\SLAMIBotApp` 处于 `codex/native-compose-filament` 正常分支且工作树
  干净；旧快照仅保留作只读参照。
- 搜索 APP 生产源码，确认没有继续把 19090 作为客户端默认值。
- `nginx -t` 通过，并确认 `/rosbridge` 的最终展开配置指向 9090。
- 检查 entrypoint，确认 19090 节点名唯一且启动失败能被检测。

### 9.2 Jetson 运行验证

同时验证：

- `ss -lntp` 显示 9090 与 19090 均监听；
- ROS 节点同时存在 `/rosbridge_websocket` 与 `/scout_nav_rosbridge`；
- `/health` 返回 `rosbridgeConnected:true`；
- 从独立客户端分别连接 9090 和 19090，查询 Topic 成功；
- 仅重启 `scout-nav` 后，两套节点仍同时存在，9090 不掉线；
- WEB 的 `/rosbridge` WebSocket 成功升级，并显示“rosbridge 已连接”；
- APP 在热点 `192.168.117.6` 与公司 Wi-Fi 当前地址下均使用 9090；
- 导航模式启动后，APP 和 WEB 均能收到 `/map`、`/global_cloud_navigation`、
  `/robot_map_pose`；
- 雷达、IMU、三路 OAK 相机 Topic 仍可通过客户端 9090 访问。

### 9.3 功能联调

在机器人静止、急停可用的安全条件下验证：

- APP 与 WEB 的地图列表、点位、任务、建图/导航模式切换；
- 地图、点云、机器人位姿实时显示；
- 非运动控制与状态 Topic；
- 需要发送速度或导航目标的测试，必须在人工确认环境安全后单独执行。

## 10. 验收标准

以下条件全部满足才可宣称完成：

1. APP 运行时实际连接 9090，不只是界面显示 9090。
2. WEB `/rosbridge` 实际反代到 9090。
3. FastAPI/nav_api 实际连接 19090，且 `/health` 为已连接。
4. 两套 rosbridge 节点名不同，重复重启 `scout-nav` 不再出现同名 shutdown。
5. APP、WEB 和导航后端均能访问其所需 ROS Topic/Service。
6. 关键 APP/WEB 功能完成真机联调，跳过项必须明确记录原因。
7. 未覆盖、删除或提交当前恢复中的地图和用户已有 nav_api 修改。

## 11. 回滚

- APP：回退仅包含默认端口修改的独立提交，重新构建上一版本 APK。
- WEB/Nginx：恢复 `/rosbridge` 到修改前配置并重建镜像。
- 导航容器：停止新容器，恢复预先保留的旧镜像/旧容器；地图与数据库 bind mount 保持
  不变。
- 回滚后重新核对 80、5000、9090、19090、ROS 节点和 `/health`，不以容器 `Up` 作为
  唯一成功判据。
