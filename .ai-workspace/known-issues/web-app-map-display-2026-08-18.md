---
id: web-app-map-display-2026-08-18
title: 前端地图不显示 / 点位无法标注（WEB + 原生 APP）根因报告
date: 2026-08-18
status: SUPERSEDED
scope: read-only analysis
verifier_pending: no
superseded_by:
  - ../decisions/ADR-0002-d360-dual-rosbridge-ports.md
  - ../../docs/superpowers/specs/2026-08-19-d360-dual-rosbridge-design.md
related_repos:
  - SLAMIBotApp
  - d360_nav2D
---

# 报告：WEB 端导航页 + APP 端点位管理看不到地图 / 无法标注

> **2026-08-19 修正：本报告保留为历史分析，端口/IP 结论不得继续作为当前事实使用。**
> `192.168.117.6` 是 Jetson 热点地址，`192.168.31.135` 是公司 Wi-Fi 当前 DHCP 地址，二者
> 都有效；Android APP 与 WEB 客户端统一使用 9090，只有 FastAPI/nav_api 内部使用 19090。
> 当前权威事实见 `facts/frontend_api.yaml`、`facts/rosbridge_profile.yaml` 与 ADR-0002。

> 任务编号：TASK-2026-08-18-001（只读 Explorer，无任何业务代码改动）
> 报告人：Claude（EXPLORER）
> 接收人：另一个 dev agent（负责修复）

---

## 0. 现象复述（用户原话）

1. 访问 `http://192.168.31.135/app`，进入"导航控制"页，**必须**先点"建图"按钮、再点"导航"按钮，才会显示**默认点云地图**；否则地图不显示、不能标点、不能导航。
2. 手机 APP 端（在调试分支 `codex/native-compose-filament`，纯 Kotlin+Compose+Filament，原生非 WebView 套壳）在"点位管理"页**看不到地图**，无法标点。

预期：**进入页面就显示默认地图**（无需手动按任何按钮）。

> **范围说明**：本次只覆盖 WEB（SLAMIBotApp/web）和 APP 当前调试分支（codex/native-compose-filament）。`SLAMIBotApp` `main` 分支（旧的 WebView 套壳版）**不在用户当前调试范围**，但其问题与 WEB 端同源（旧 assets 资源继承自错误构建产物），结论放 §7.3 备查。

---

## 1. 三层事实速览

### 1.1 服务端实际跑法（板上 scout-nav 容器，Dockerfile + docker-entrypoint.sh）

| 端口 | 服务 | 来源 |
|---|---|---|
| **80** | Nginx（同源反代 `/api /health /mcp /rosbridge`） | `d360_nav2D/docker-entrypoint.sh:48` |
| **5000** | FastAPI（MCP + REST） | `d360_nav2D/docker-entrypoint.sh:91` |
| **19090** | rosbridge_server | `d360_nav2D/docker-entrypoint.sh:23`（`rosrun rosbridge_server rosbridge_websocket _port:=19090`） |
| 11311 | ROS Master | `ROS_MASTER_URI=http://127.0.0.1:11311` |
| can0 | Scout mini 底盘 CAN，500k bit/s | 现场 |
| **板上 LAN IP** | **192.168.31.135**（DHCP，旧文档写 192.168.31.132 失效） | `facts/jetson_profile.yaml:31` |

### 1.2 Nginx 反代的关键一行

`d360_nav2D/frontend/deploy/nginx.conf:41-48`：

```nginx
location /rosbridge {
    proxy_pass http://127.0.0.1:19090;
    # proxy_pass http://127.0.0.1:9090;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
}
```

**板上明确把 9090 那行注释掉，只暴露 `/rosbridge` 经 80 端口反代到 19090。**

### 1.3 SLAMIBotApp 客户端的实际写法（全部是错的）

| 文件：行 | 写法 | 错误性质 |
|---|---|---|
| `SLAMIBotApp/web/src/NavigationModule.tsx:20` | `rosbridgeUrl={\`ws://${rosServerIp}:9090\`}` | **① 绕开 Nginx 80 反代，② 端口 9090 上没有任何服务** |
| `SLAMIBotApp/web/src/runtimeConnection.ts:2` | `FALLBACK_ROBOT_HOST = "192.168.117.6"` | **板上 LAN IP 是 192.168.31.135，不是 192.168.117.6** |
| `SLAMIBotApp/web/src/runtimeConnection.ts:43-45` | `getRosbridgeUrl` 硬编码 `:9090` | 同 ① |
| `SLAMIBotApp/web/src/App.tsx:25,61,144,164,317` | `connectToROS(\`ws://${rosServerIp}:9090\`)` 与 `DEFAULT_ROS_SERVER = getRobotHost()`（吃上面错误的 host） | 同 ①② |
| `SLAMIBotApp/web/.env.production` | `VITE_ROS_SERVER=192.168.117.6` | 同 ② |

### 1.4 npm 包（私有包，源码在 `d360_nav2D/frontend`）的实际写法（正确的）

| 文件：行 | 写法 | 评价 |
|---|---|---|
| `d360_nav2D/frontend/src/runtime/config.ts:19-25` | **默认** `ws://${location.host}/rosbridge`（走 Nginx 80 反代） | ✓ 这是板上正确的连接方式 |
| `d360_nav2D/frontend/README.md:39-45` | **示例** `rosbridgeUrl="ws://192.168.117.6:9090"` | ✗ **官方 README 自带的示例也是错的**，误导读者 |
| `d360_nav2D/frontend/src/ros/topics.ts` | 默认订阅 `/map`（2D 底图）、`/global_cloud_navigation`（3D 点云）、`/robot_map_pose`（机器人位姿） | （需要核 topic 是否在线） |

### 1.5 Web 端连接的"门"机制

`SLAMIBotApp/web/src/NavigationGate.tsx`：

```ts
if (health.status === "online") admitted.current = true;
if (!admitted.current) return <Navigate to="/" replace />;
```

门控：`robotHealth.status === "online"` 才允许进入 `/navigation/*`。

`SLAMIBotApp/web/src/robotHealth.ts:35,44-48`：

```ts
const response = await fetch(`${base}/health`, { signal });
// ...
const robotConnected = dogConnected ?? rosbridgeConnected;
return { status: robotConnected ? "online" : "offline", ... };
```

`/health` 来自后端 FastAPI：`d360_nav2D/src/nav_api/fastapi_service/app.py:92-98`：

```python
@app.get("/health")
def health() -> dict:
    return {"success": True, "service": "nav-api-fastapi", "rosbridgeConnected": ros_client.is_connected,}
```

**关键**：`ros_client.is_connected` 在后端是看 `roslibpy.Ros(host=127.0.0.1, port=19090).is_connected`（`ros_client.py:18-22,34-36`）。**后端进程成功连上板上 19090 rosbridge 后**，`/health` 才返回 `rosbridgeConnected=true`，前端才允许进入 `/navigation`。

**事实源明确将 rosbridge 端口记为 `current: 19090`，`target: 9090`（`facts/rosbridge_profile.yaml`），并标注 main 分支 App 仍连 9090、codex/native-compose-filament 已改 19090，但 APP 与 WEB 端代码改动并未跟着后端一起调整。**

---

## 2. 根因（WEB 端，确认）

### 根因 A：**SLAMIBotApp 客户端连错了 rosbridge 地址**

**证据强度**：3 处独立证据互相印证（Nginx 配置 / docker-entrypoint / npm 包默认 URL）

1. 板上 rosbridge 实际跑在 **19090**，Nginx 反代到 `/rosbridge` 路径。
2. SLAMIBotApp 的 `NavigationModule.tsx:20` 显式传入 `ws://${rosServerIp}:9090`（**错端口 + 绕开 Nginx**）；`runtimeConnection.ts` 默认 host 也是错的。
3. 由于 SLAMIBotApp 是显式传入，`runtime/config.ts:33-40`（`normalizeNavigationRuntime`）trim 后直接采用入参，**npm 包内置的"走 Nginx `/rosbridge`"默认行为被完全覆盖**。
4. `WebView` / 浏览器开控制台应能看到 `WebSocket connection to 'ws://...:9090/' failed`。

### 根因 B：**默认 ROS 服务器 IP 写错**

**证据强度**：`facts/jetson_profile.yaml:31` 明确 `jetson_lan_ip: 192.168.31.135`，但 `runtimeConnection.ts:2` 与 `.env.production` 都写 `192.168.117.6`（开发期另一台机的 IP）。

**实际影响**：即便用户手动改 ROS 服务器 IP（主页"🔌"按钮弹框 → `customPrompt`），仍可填到正确 IP，但是 npm 包入场规则会把 `192.168.117.6` 当作生产默认值，**首次进入 / 切回生产构建时都中招**。

### 根因 C：**npm 包 README 的示例也是错的**

**风险**：`d360_nav2D/frontend/README.md:39-45` 写的是 `rosbridgeUrl="ws://192.168.117.6:9090"`。这不是 npm 包的默认行为（`config.ts` 默认是 `/rosbridge`），而是 README 给读者的示例，**示例本身**就指错了方向。已观察到至少 SLAMIBotApp 是按这个示例抄过去用的，说明这条误导链已扩散。

---

## 3. "必须先建图再导航才显示地图"的合理解释

**`ModePanel.tsx:42-43`** 的两个按钮都调 HTTP（并非订阅）；按钮对应的后端动作（`process_manager.switch_to_mapping()` / `switch_to_navigation()`）：

- **建图模式** → 后端 `process_manager` 启 `gmapping.launch` 或 FAST_LIO → ROS 上线 `/global_cloud*`、`/map`（如果是 gmapping 边建边出）等。
- **导航模式** → 后端启 `my_nav_launch.launch`（move_base + amcl + map_server）→ ROS 上线 `/map`（`nav_msgs/OccupancyGrid`）、`/amcl_pose` 等。

Dashboard 主页（`DashboardPage.tsx:68`）渲染的是 `<Viewer3D />`（详见 `Viewer3D.tsx:46-55`），订阅的是 `TOPICS.mapCloud.name`，即 **`/global_cloud_navigation`**（`topics.ts:10`）。这个 topic 由**导航栈**发布，在**导航模式启动**后才有数据。所以：

- 只点"建图"：仅 FAST_LIO 在跑，nav 栈没启动，**点云地图不出现**。
- 只点"导航"：nav 栈启动，先建过的 PCD 经 `/global_cloud_navigation` 发布，Dashboard 看到点云。
- **先点建图 → 再点导航**：与"只点导航"的差别主要在后端进程切换的时序与缓存；更可靠的解释是**用户的观察对应了实际 nav 栈加载过程慢/initial pose 等因素的延迟**。

**而更深的真相是**：由于根因 A,B 让 rosbridge 客户端在浏览器里始终连不上，**根本看不到任何 RT 数据**；用户感知到的"按这两个按钮就会显示地图"很可能是**某次 retry/时序成功连上后，被误以为是按钮触发的**；后续 dev agent 修复 A,B 之后，光"进页面"就应该有数据，无需按任何按钮。

> 这条解释属于**推测**：实际触发顺序需要在修复 rosbridge 连接后，在前端 DevTools 看 `NavStatus`/`Connection bar` 与 `/map`、`/global_cloud_navigation` topic 的实时订阅情况证实。

---

## 4. APP 端根因（codex/native-compose-filament 分支，HEAD=f919874）

> 本节是**修正版**。此前 §4 误把 codex 分支当作"已修好、无 A/B 问题"，基于错误前提"APP 是 main 分支 WebView 套壳"。事实是用户当前调试的就是 codex 分支，**它也存在独立的连接配置错误，且首装即触发**。

### 4.1 代码路径事实链（从用户配置到 socket）

```
NativeHomeController                        # 持有 SharedPreferences，初始 host 与持久化
  ↓ state.endpoint
SlamibotApp                                 # 把 endpoint 串到 controlSession
  ↓
NativeControlSession                        # RosbridgeSession（低频 JSON 控制 socket）
  ↓
NativeNavigationSession                     # 启动时主动 connect 两条独立 socket
  ├─ NativePointCloudClient.connect(url, "/global_cloud_navigation")     # 3D 点云（CBOR）
  └─ NativeOccupancyGridClient.connect(url)                              # 2D 占据栅格（/map，CBOR）
  ↓
NativeNavigationScreen → NativeNavigationPointsPage(NavigationMapPreview)  # "点位"页右侧地图
```

### 4.2 关键证据

**① 默认 host 写错（与板上事实矛盾）**

`SLAMIBotApp_codex/app/app/src/main/java/com/example/metacam/RobotEndpoint.kt:30-36`：

```kotlin
companion object {
    const val DEFAULT_HOST = "192.168.117.6"
    const val DEFAULT_ROSBRIDGE_PORT = 19090          // 端口对
    const val DEFAULT_API_PORT = 5000                   // 对
    const val DEFAULT_FIRMWARE_PORT = 5001
    ...
    val Default = RobotEndpoint(DEFAULT_HOST)         // ← 错 host
}
```

- `DEFAULT_HOST = "192.168.117.6"` 与 `facts/jetson_profile.yaml:31`（`jetson_lan_ip: 192.168.31.135`）**冲突**。
- 端口 19090 ✓（已对照 docker-entrypoint 与 rosbridge_profile）。
- 端口 5000 ✓（FastAPI 实际监听端口）。

**② 首次启动即触发错误默认值（无任何用户操作）**

`SLAMIBotApp_codex/app/app/src/main/java/com/example/metacam/NativeHomeController.kt:53-55`：

```kotlin
private val initialEndpoint = runCatching {
    RobotEndpoint.parse(preferences.getString(HOST_KEY, null).orEmpty())  // 首次：prefs 为空 → ""
}.getOrDefault(RobotEndpoint.Default)                                     // → 192.168.117.6
```

- SharedPreferences key `robot_host`、文件名 `slamibot_native_runtime`（同文件 `:120-122`）。
- **装机后首次启动** / **用户清空 APP 数据** → 上述路径必然走到 `RobotEndpoint.Default = 192.168.117.6`，**任何自定义 host 都不会生效**。
- `setEndpoint(value: String)`（`:71-75`）和 `setEndpoint(endpoint: RobotEndpoint)`（`:77-81`）只有用户主动改 host 时才会被调；**没有任何自动探测/纠正机制**。

**③ 错的 endpoint 直接灌进两条独立 rosbridge socket**

`SLAMIBotApp_codex/app/app/src/main/java/com/example/metacam/NativeNavigationSession.kt:92-93`：

```kotlin
pointCloudClient.connect(endpoint.rosbridgeUrl, D360Topics.Navigation.pointCloud.name)
occupancyGridClient.connect(endpoint.rosbridgeUrl)
```

- `endpoint.rosbridgeUrl = "ws://$host:$rosbridgePort"`（`RobotEndpoint.kt:25`）。
- `endpoint.host = 192.168.117.6`（错） → 两条 socket 都连 `ws://192.168.117.6:19090`。
- WebSocket 永远连不上 → 重连退避到 10s（`NativePointCloudClient.kt:121`、`NativeOccupancyGridClient.kt:139`），但仍然连不上。
- 后果：`occupancyGrid` 永远 `null`，`pose2D` 永远 `null`，`/global_cloud_navigation` 永远无数据 → Native PointCloud + Filament 渲染均为空。

**④ host 编辑弹窗的 placeholder / 提示文案又误导**

`SLAMIBotApp_codex/app/app/src/main/java/com/example/metacam/NativeHomeScreen.kt:298-323`：

```kotlin
OutlinedTextField(
    ...
    placeholder = { Text("192.168.117.6") },         // ← 错 host 当 placeholder
    supportingText = {
        Text(error ?: "ws://$host:9090", ...)        // ← 9090 错（板上 19090）
    },
)
```

- 用户即使发现"主页显示设备未连接"、进"🔌 连接设备"弹窗手动改 IP，**弹窗默认填充 / 提示都还在暗示 `192.168.117.6:9090`**。
- 这条文案与 `RobotEndpoint.kt` 默认值同源（与事实源 `facts/jetson_profile.yaml:31`、`facts/rosbridge_profile.yaml:15` 冲突）。

**⑤ "点位"页实际渲染逻辑：依赖 occupancyGrid = null 时必空**

`SLAMIBotApp_codex/app/app/src/main/java/com/example/metacam/NativeNavigationPages.kt:77-201`：

```kotlin
fun NativeNavigationPointsPage(
    state: NativeNavigationUiState,
    controller: NativeNavigationController,
    occupancyGrid: NavigationOccupancyGrid?,    // ← 来自 session.occupancyGrid
    robotPose: NavigationPose2D?,               // ← 来自 session.pose2D
    ...
) {
    ...
    NavigationMapPreview(
        ...
        occupancyGrid = occupancyGrid,
        robotPose = robotPose,
        ...
    )
}
```

- `NativeNavigationScreen.kt:336-344` 把 `session.occupancyGrid` 与 `session.pose2D` 透传。
- 两者都从 socket 喂入；socket 连不上 → 都 `null`。
- `NavigationMapPreview` 拿 `null` 的 grid → **点位页右侧整张地图不渲染**，标点所需的"世界坐标 ↔ 像素坐标"换算（`NavigationOccupancyGrid.worldToBitmap`、`bitmapToWorld`，见 `NavigationOccupancyGrid.kt:39-56`）**全部失效** → "无法标点"。
- `navigationController.navigateTo(...)` 等命令走 HTTP（`/api/navigation/...`），**理论上可发**，但：
  1. HTTP 也连错 host（`endpoint.apiBaseUrl = http://192.168.117.6:5000`），无法联通；
  2. 即便联通，标点选取本身就是"看地图点一下"，地图没有 → 无法生成 (x, y) → 走不通；
  3. 进入 Points 页面前 `NativeHomeController.probeCurrentEndpoint()` 已经把状态打成 Offline（见 ⑥），`NativeHomeScreen.kt:113-118` 把"导航控制"卡显示为 Offline，**整个导航入口可能被 UI 隐藏或置灰**。

**⑥ 主页"设备未连接"判定：同一 host 错了**

`SLAMIBotApp_codex/app/app/src/main/java/com/example/metacam/NativeHomeController.kt:88-109`：

```kotlin
private fun probeCurrentEndpoint() {
    val endpoint = mutableState.value.endpoint
    val decoded = runCatching {
        val request = Request.Builder().url("${endpoint.apiBaseUrl}/health").get().build()
        //                                          ↑ http://192.168.117.6:5000/health （错）
        ...
    }
    ...
    mutableState.value = if (decoded == null) {
        NativeHomeState(endpoint, NativeRobotHealthStatus.Offline)
    } else { ... }
}
```

- `apiBaseUrl` 由 `RobotEndpoint.apiBaseUrl` 派生（`RobotEndpoint.kt:26`），同样吃错 host。
- `/health` 也连不上 → `healthStatus = Offline` → `NativeHomeScreen.kt:113-118` 顶卡显示"设备未连接" → `rosConnected = false`（`SlamibotApp.kt:37`）→ `rosbridgeConnection` 链路状态都呈红色。

### 4.3 codex 分支的事实链（一句话总结）

**APP 首次启动 / 清数据后：`NativeHomeController` 从空 SharedPreferences 兜底到 `RobotEndpoint.Default = RobotEndpoint(192.168.117.6, 19090, ...)` → SlamibotApp 把这个 endpoint 串到 `NativeControlSession` 与 `NativeNavigationSession` → 两条独立 rosbridge socket（`NativePointCloudClient` + `NativeOccupancyGridClient`）都连错 IP → `/map`、`/global_cloud_navigation`、`/robot_map_pose` 均无数据 → `NativeNavigationPointsPage` 拿到的 `occupancyGrid` 与 `robotPose` 始终 `null` → "点位"页看不到地图、无法标点、"导航"卡显示离线。**

> 与 WEB 端不同之处：APP 端的连接 URL 本身（`ws://192.168.117.6:19090`）**端口是对的**，错的是 host。这条路径**完全独立于 WEB 端**，与 SLAMIBotApp/web 的 `NavigationModule.tsx` 没有任何代码共享。

---

## 5. 修复方向（给另一个 dev agent，**仅建议，未授权**）

### 5.1 WEB 端（最小修改）

| 文件 | 当前 | 建议 |
|---|---|---|
| `SLAMIBotApp/web/src/NavigationModule.tsx:20` | `rosbridgeUrl={\`ws://${rosServerIp}:9090\`}` | **删除该 prop，改用 npm 包默认**（走 `ws://${location.host}/rosbridge`） |
| `SLAMIBotApp/web/.env.production` | `VITE_ROS_SERVER=192.168.117.6` | **改成 `192.168.31.135`**（或让它留空，完全交给用户在主页改） |
| `SLAMIBotApp/web/src/runtimeConnection.ts:2` | `FALLBACK_ROBOT_HOST = "192.168.117.6"` | 同上，或让它走 `.env.production` 的值 |
| `SLAMIBotApp/web/src/runtimeConnection.ts:43-45` | `getRosbridgeUrl` 强制 `:9090` | **可删；已不再被 `NavigationModule` 需要** |
| `SLAMIBotApp/web/src/App.tsx` 多处 `ws://...:9090` | 同上 | **保留主页 connect 按钮**（主页采集页 `/view` 还是用本地 ROS 直连点云，这点与导航页不同） |

### 5.2 WEB 端（更彻底）：统一经 Nginx `/rosbridge` 走 80 反代

只需保证环境里 `VITE_ROS_SERVER` 与 `location.host` 同源即可，**免去跨域/端口不一致的隐性雷**。`d360_nav2D/frontend/` 的 npm 包默认就是这条路径。

### 5.3 APP 端（codex 分支，最小修改）

| 文件 | 当前 | 建议 |
|---|---|---|
| `RobotEndpoint.kt:30` | `const val DEFAULT_HOST = "192.168.117.6"` | **改成 `"192.168.31.135"`**（与 `facts/jetson_profile.yaml:31` 对齐） |
| `RobotEndpoint.kt:36` | `val Default = RobotEndpoint(DEFAULT_HOST)` | 同步生效（仅依赖 `DEFAULT_HOST`） |
| `NativeHomeScreen.kt:303` | `placeholder = { Text("192.168.117.6") }` | **改成 `"192.168.31.135"`** |
| `NativeHomeScreen.kt:319` | `Text(error ?: "ws://$host:9090", ...)` | **改成 `"ws://$host:19090"`** |
| `NativeHomeController.kt:53-55` | `getOrDefault(RobotEndpoint.Default)`（空 prefs 直接兜底） | （可选）在 prefs 为空时先 `probeCurrentEndpoint()`，若失败再降级到 `Default`；或加"启动探测 / 健康检查结果回填"逻辑 |

### 5.4 APP 端（加固建议）

- **`NativeHomeController` 启动后主动 `probeCurrentEndpoint()`**（已有，line 60-69），探测失败时把 `healthStatus` 显示为 `Offline`，**已实现**（`:88-109`）。建议在弹窗里对用户明确提示"当前地址 192.168.117.6 不可达，是否使用 192.168.31.135 重试？"，降低首次配置门槛。
- **`NativeOccupancyGridClient` / `NativePointCloudClient`** 的连接逻辑本身**没问题**（CBOR 解码、JSON 回退、重连退避都齐），无需修改。修完 host 后，**只要 ROS 那边 `/map` 与 `/global_cloud_navigation` topic 在线，点位页应当自动出图**。
- **`RosbridgeSession`** 的 `throttle_rate = 50` 对低频控制 topic 没问题；对 `/map`（1Hz 量级）也无影响；`NativeOccupancyGridClient` 走独立 socket 是正确设计。

### 5.5 共同清理

`d360_nav2D/frontend/README.md:39-45` 的示例同步改成 `rosbridgeUrl="ws://YOUR_ROS_IP/rosbridge"`（走反代）或留空用默认。这条不属于阻塞，但能避免后人再抄错。

---

## 6. 验证步骤（只读，**需用户协助上板**）

### 6.1 服务端基础（WEB / APP 都依赖）

```bash
# SSH 上 Jetson (jetson@192.168.31.135) — 板上事实
ssh jetson@192.168.31.135
docker exec -it scout-nav bash

# 1) rosbridge 进程与端口
ss -lntp | grep 19090        # 应有 rosbridge_websocket
tail -100 /tmp/rosbridge.log

# 2) 后端 FastAPI /health
curl -s http://127.0.0.1:5000/health
# 期望: {"success":true,"service":"nav-api-fastapi","rosbridgeConnected":true}

# 3) 经 Nginx 80 反代 /health (等于前端访问路径)
curl -s http://192.168.31.135/health | jq .
# 期望同上

# 4) /rosbridge 是否升级头可达 (HTTP 101 / 400 即可,不是端口拒接)
curl -i --http1.1 -H 'Upgrade: websocket' -H 'Connection: Upgrade' \
     -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGVzdA==' \
     http://192.168.31.135/rosbridge/

# 5) ROS 关键 topic 是否真的发布(决定前端能否渲染地图)
source /opt/ros/noetic/setup.bash
timeout 5 rostopic echo -n 1 /map                   # 2D 底图(nav_msgs/OccupancyGrid)
timeout 5 rostopic echo -n 1 /global_cloud_navigation  # 3D 点云(需 navigation 模式)
timeout 5 rostopic echo -n 1 /robot_map_pose            # 机器人位姿(后端转发 /amcl_pose)
timeout 5 rostopic echo -n 1 /amcl_pose
```

### 6.2 WEB 端 DevTools 验证

- 控制台：`WebSocket connection` 报错应消失。
- Network → WS：应有一条 `ws://192.168.31.135/rosbridge`（注意路径 `/rosbridge`，不是 `:9090`）
- 一进入 `/navigation/*`，不需要任何点击，右侧 ConnectionBar 应为"已连接"，2D 占据栅格应自动渲染。

### 6.3 APP 端（codex 分支）ADB 日志验证

```bash
# 1) 连上 Android 设备 / 模拟器
adb devices

# 2) 清空 APP 数据（验证首次启动场景）
adb shell pm clear com.example.metacam.debug    # 或 com.example.metacam

# 3) 启动 APP，过滤关键 tag
adb logcat -c
adb shell am start -n com.example.metacam.debug/com.example.metacam.MainActivity
adb logcat -v time \
    OccGridCbor:V \
    OccupancyGridClient:V \
    NativePointCloud:V \
    RosbridgeSession:V \
    MetaCamHome:V \
    *:E

# 期望日志：
#   - OccupancyGridClient: Occupancy-grid subscribe (cbor): /map
#   - NativePointCloud:    Point-cloud subscribe (json): /global_cloud_navigation
#   - RosbridgeSession:    Native control session connected: ws://192.168.31.135:19090
#   - 无 "connection failed" / "ECONNREFUSED"
```

### 6.4 APP 端 UI 行为验证

- **首次启动 / 清数据后**：主页顶卡应显示"设备已连接"（绿条），无需用户先到弹窗改 host。
- **进入"导航控制" → 点"点位"**：右侧 `NavigationMapPreview` 应自动渲染 2D 占据栅格底图，左侧 `MapList / PointList / AreaList / TaskList` 可切换。
- **进入点位页 → 在地图上点一下**：应进入标点流程（`MapPreviewMode.AddPoint` → `onWorldTapped` → 弹出点位命名对话框）。
- **"设备未连接"复现路径**：故意把 host 改回 `192.168.117.6` → 主页顶卡应立即变 Offline，"导航控制"入口可能被隐藏/置灰，作为对照验证。

### 6.5 主页 host 编辑弹窗验证

- 进入主页 → 右上 🔌 → "连接设备" 弹窗。
- placeholder 文本应为 `192.168.31.135`（修复后），下方提示文本应为 `ws://192.168.31.135:19090`（**注意 19090，不是 9090**）。

---

## 7. 风险与边界

### 7.1 严格遵守的不变量

- **不动** d360_nav2D 的 launch / rosbridge / NavCommand srv / nav_api 后端接口（`protected_interfaces`）—— 当前修复只在 SLAMIBotApp/web 与 SLAMIBotApp_codex 客户端代码。
- **不动** Nginx / Docker / ROS 环境。
- **不改** `ConnectionControl` 相关状态机——只是单纯修连接配置，不动 UI/状态。
- 不需要 `migration: true`；这次不是 ROS1↔ROS2 的事，纯客户端连接串。

### 7.2 延伸风险

- WEB：`runtimeConnection.ts` 的 `getRosbridgeUrl` 函数若删除，需先查它是否仍被别处引用（本报告未做完整反向引用扫描，留为待办）。
- WEB：主页 `/view` 的 `View.tsx:568` 仍硬编码 `ws://${rosServerIp}:9090` 给采集页的 PointCloud 订阅。该页是页面独立功能，但**它走的也是同一个不存在的 9090**——用户说"采集页能投影点云"吗？**没有证据**，需要后续 dev agent 在主页一起确认。
- APP（codex）：`NativeHomeController` 的 `RobotEndpoint.parse("")` 失败兜底到 `RobotEndpoint.Default` 这条路径，**修 host 常量后仍然安全**（只是默认值变了）；若要更激进（探测失败时弹窗建议正确 host），需要单独设计。
- APP（codex）：`NativeOccupancyGridClient` 的 CBOR 解码器是手写的（`NativeOccupancyGridClient.kt:173-296`），只解必要字段；若 ROS 那边 `/map` 字段集变化（例如 origin 多了 `orientation` 或 `info` 多了 `map_load_time`），需要扩展该解析器；当前实现已覆盖 `info.{width, height, resolution, origin.{position, orientation}}` 与 `data` 数组。

### 7.3 受本报告影响的事实源文件

- `facts/frontend_api.yaml`（`rosbridge_port.current` / `rosbridge_port.main_branch` / `rosbridge_port.codex_branch`）目前是基于"main 分支仍是 9090"的事实；**修复后**应同步更新。
- `facts/rosbridge_profile.yaml`（`port_note` 中 `App 分支差异`）也应注明"main 分支客户端已改为走 /rosbridge 反代，codex 分支客户端已修 host 默认值"。

### 7.4 SLAMIBotApp `main` 分支（旧的 WebView 套壳版）

- 用户当前调试的是 codex 分支，main 分支**不在本次范围**。
- 但若以后重新启用 main 分支：与 web 端共坑（同一份 `NavigationModule.tsx:20` + `runtimeConnection.ts:2` 错误），修复方式同 §5.1，重新 `npm run build:release` → `build.sh` 重新打包 → APP assets 更新。

---

## 8. 待办（留给 dev agent 与上板验证者）

- [ ] DEV（WEB）：按 §5.1 改 `SLAMIBotApp/web/src/NavigationModule.tsx`、`runtimeConnection.ts`、`.env.production`（提 PR）。
- [ ] DEV（WEB）：`SLAMIBotApp/web/build:release` 重打 → 同步 `build.sh` → 进 `app/assets/web/`。
- [ ] DEV（APP/codex）：按 §5.3 改 `RobotEndpoint.kt:30`、`NativeHomeScreen.kt:303,319`。
- [ ] DEV（APP/codex，可选加固）：`NativeHomeController.kt` 增加"探测失败时弹窗推荐正确 host"逻辑。
- [ ] VERIFY（服务端）：上板跑 §6.1 五条命令，贴结果。
- [ ] VERIFY（WEB）：浏览器 DevTools 看 WS 与 2D/3D 地图自动渲染。
- [ ] VERIFY（APP/codex）：清数据后 adb logcat 跑 §6.3；UI 上跑 §6.4。
- [ ] DOC：更新 `facts/frontend_api.yaml` 与 `facts/rosbridge_profile.yaml` 端口/分支差异。
- [ ] DOC：`d360_nav2D/frontend/README.md` 示例改正。
- [ ] （可选）看 `View.tsx:568` 主页点云订阅是不是也要修。
