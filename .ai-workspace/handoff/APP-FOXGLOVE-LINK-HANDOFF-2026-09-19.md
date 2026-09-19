# APP 改造交接：D360 / D360S 客户端链路切到 Foxglove（ROS1 `ros1` 二进制）

- 日期：2026-09-19
- 交接对象：负责改 APP 的另一个 AI（+ 用户）
- APP 仓库：`F:\SLAMIBotApp`，分支 `codex/native-compose-filament`（基线 `864b537`）
- 服务端状态：**已改完并推云，不要改服务端**（固件仓分支 `codex/d360-foxglove-link-20260919`，HEAD `95dac0f`）
- 测试安排：上班后 D360 与 D360S **一起真机联调**（不存在"APP 未改导致黑屏阻塞"的顾虑）

---

## 1. 目标

把 APP 的 ROS 链路从「rosbridge JSON + cbor-raw 专属 socket」换成 **Foxglove WebSocket 协议**（D360 走 `ros1` 二进制编码），视频统一到一个 HTTP **MPEG-TS/H.264** 端点；删掉所有旧协议/旧端点代码，不留兼容层。最终同一份 APP 既能连 D360（ROS1）也能连 D360S（ROS2）。

## 2. 服务端已定的契约（实现依据）

| 项 | 值 |
|---|---|
| 控制链路 | `ws://<host>:9090`，subprotocol **`foxglove.websocket.v1`**（原 rosbridge 同端口） |
| D360 通道编码 | **`encoding: "ros1"`**（ROS1 原生线序；schema 为 ROS1 `.msg` 全文，依赖定义用 `====` 分隔） |
| D360S 通道编码 | **`encoding: "cdr"`**（ROS2 CDR：4 字节封装头 + 对齐规则） |
| 服务调用 | 请求/响应都是 **JSON**；schema 为 `.srv` 的 request/response 文本 |
| 参数 | `parameters` capability（控制台用它读 `/device_type`） |
| 客户端发布 | **只接受 `ros1`**（D360）：`/cmd_vel_web` 必须自己按 ROS1 线序序列化 |
| 视频 | **唯一**端点 `http://<host>:5010/api/camera/preview.ts`：**H.264（x264 软编，ultrafast+zerolatency）封成 MPEG-TS**，`Content-Type: video/mp2t`；三路拼接 B,A,C、10fps、1 秒一个关键帧、无客户端时不编码；`/api/camera/preview.ts/status` 报 clients/fps/码率/ffmpeg 状态 |
| `/keyframe` | **已删除**（连同 `oak_keyframe_stitcher` 节点与编译注册一起删）→ APP 的 fallback 必须删，没有兜底 |
| `/topic_frequencies` | 仍是 `std_msgs/String` 内嵌 JSON，键 **`/keyframe` → `/SLB_CAM_A/compressed`** |
| HTTP API | 5000（导航 `nav_api`）/ 5001（固件 / 控制台 / OTA）**不变** |

## 3. APP 现状盘点（已核实）

| 文件 | 行数 | 现在用的协议 | 改造后 |
|---|---|---|---|
| `RosbridgeSession.kt` | 395 | 手写 rosbridge JSON（subscribe/publish/callService/throttle） | 换成 Foxglove 客户端 |
| `NativeControlSession.kt` | 69 | 共享低频 owner（状态主题 + 服务） | 复用结构，底层换 Foxglove |
| `NativePointCloudClient.kt` | 242 | 独立 OkHttp WS + `compression:"cbor-raw"` | 独立 Foxglove 连接订阅（**保留点云单独一条连接**的隔离设计） |
| `NativeOccupancyGridClient.kt` | 558 | 同上抓 `/map` cbor-raw + 自带 CBOR 解码 | 独立连接订阅；CBOR 解码器废弃，改按 ROS1 线序解析 |
| `NativeNavigationSession.kt` | 455 | nav 会话（MjpegStreamClient + rosbridge） | 同上；视频换成 MPEG-TS 播放 |
| `NativeDataCollectionSession.kt` | 592 | 采集：点云 + FAST_LIO 位姿 + **`/keyframe` fallback** + MJPEG 预览 | 删 fallback；视频只留 5010 的 MPEG-TS |
| `MjpegStreamClient.kt` | 208 | HTTP MJPEG（OkHttp） | **删除**：改用 ExoPlayer（`MimeTypes.VIDEO_MP2T`）播同一个 URL；若坚持手写，也只需按 TS 包解析，不再处理 multipart |
| `D360ApiClient.kt` | 140 | HTTP 5000 API | 不变 |
| `NativeFirmwareController.kt` | 453 | 5001 + rosbridge | 5001 不变；rosbridge 部分改 Foxglove |
| `AndroidGamepadController.kt` | 347 | 手柄/触控 → 发 `/cmd_vel_web` | 走 Foxglove 客户端发布（`ros1` 编码） |
| `D360Topics.kt` | 47 | 主题/类型中心表 | **不用改**（名字与类型不变） |
| `RobotEndpoint.kt` | 62 | 端口常量：9090/5000/5001/5010 + `cameraStreamUrl`(5000)/`videoLinkCameraStreamUrl`/`cameraPreviewUrl`(5010) | **删 5000 两条**；只留 5010，且 URL 改为 `…:5010/api/camera/preview.ts`（MPEG-TS） |
| `app/app/src/main/cpp/point_cloud_decoder.cpp` | 476+ | JNI 解码 rosbridge **CBOR** 载荷 | 见 §4 资产 |

话题面（`D360Topics.kt` 与各处订阅）：`/Odometry`、`/slam_pose`、`/point_cloud`（采集款）、`/global_cloud_navigation`（导航款）、`/robot_map_pose`、`/map`、`/nav_status`、`/nav_multi/status`、`/cmd_vel_web`、`/cmd_vel`、`/odom`、`/move_base/GlobalPlanner/plan`、`/move_base/TebLocalPlannerROS/local_plan`、`/battery`、`/storage`、`/driver_status`、`/project_duration`、`/rtk/gnss`、`/rtk/satellites`。
服务面：`/get_version`、`/usb_operation`、`/project_list`、`/project_delete`、`/project_duration`、`/project_image`、`/project_control`、`/rtk/login`、`/set_camera_exposure`、`/set_camera_gain`、`/set_camera_white_balance`（+ `/get_camera_status`）。

## 4. 可复用资产（别重写）

1. **点云解析已经有一半**：`point_cloud_decoder.cpp` 已经实现「PointCloud2 → 顶点缓冲」。它现在吃的是 rosbridge `cbor-raw` 载荷（CBOR 包装 + 裸 ROS1 缓冲）；**Foxglove 的 `ros1` 编码给的就是那个裸缓冲**，所以这条链路是"拆掉外层 CBOR 包装"，不是重写。
2. `/map` 的 `parseCborOccupancyGrid` 同理：字段解析可复用，外部帧格式换成 ROS1 线序（或 CDR）。
3. 服务调用本来就是 JSON，Foxglove 服务调用也是 JSON，改动小。
4. `D360Topics.kt` 是主题/类型的单一事实源，保留。

## 5. 必须新增

1. **Foxglove WS 客户端（Kotlin，自己实现）**：握手 `foxglove.websocket.v1`；处理 `serverInfo`（读 `supportedEncodings`）、`advertise`（通道 id/encoding/schema）、binary 数据帧（订阅 id + 时间戳 + payload）、服务调用（JSON）、参数 get/set。官方**没有 Kotlin 客户端**（有 JS/Python/C++/Rust），建议用现有 OkHttp + org.json 自己写，不引第三方。
2. **按 `channel.encoding` 分派解码器**：`ros1`（D360）与 `cdr`（D360S）。CDR 是真正的新增项（封装头 + 对齐）；ROS1 是"按 `.msg` 顺序 + 小端 + 字符串/数组 4 字节长度前缀"。
3. **客户端发布 `/cmd_vel_web`**：`clientAdvertise` + 二进制客户端帧，编码必须 `ros1`。
4. schema 处理：ROS1 桥发的 `.msg` 全文可能带**前导 `====` 分隔行**（JS shim 踩过坑：会被解析成空根定义，导致每帧解成 `{}`）；ROS2 侧用 `===` 分隔。APP 只用到少数类型，可直接按已知类型硬编码字段布局（更省事、更快），但要覆盖 D360 与 D360S 两侧的类型。
5. 参考实现：JS shim `SLAMIBOT_D360/tools/foxglove-shim/src/index.js`（分支 `codex/d360-foxglove-link-20260919`）已把「连接/重连、订阅去重、节流、服务 JSON、参数读取、按 encoding 分派解码」写了一版，Kotlin 侧可照搬逻辑；其 `test/mock-foxglove.test.mjs` 里手写的 mock 桥也演示了协议帧格式。

## 6. 必须删除（不留兼容）

- `RosbridgeSession` 的 rosbridge JSON 协议实现。
- 两处 `compression: "cbor-raw"` 与 JSON 路径 `JsonPointCloudConverter`。
- `/keyframe` fallback 整套（`subscribeKeyframeFallback` / `removeKeyframeFallback` / `keyframes` channel）。
- `RobotEndpoint.cameraStreamUrl`、`videoLinkCameraStreamUrl`（5000 那两条）。
- 任何按 `/topic_frequencies['/keyframe']` 取值的代码。

## 7. 验收（真机，D360 与 D360S 各一遍）

连接建立；2D 地图与点云显示正常；遥控能动且松手能停；视频（5010）流畅不裁切；服务调用（版本/项目/相机/RTK）成功；参数读取成功；`/topic_frequencies` 正常；日志里没有 rosbridge 相关报错。测试时两设备**同一份 APK**。

## 8. 禁止

- 不改服务端（固件仓 / 导航仓）；不开新端口；不为旧协议留兼容分支；不把只在 D360 出现的 topic 名硬塞进 D360S 路径。

## 9. 跨产品缺口（需要决策，不是 APP 单独能解决的）

- **D360S 侧目前没有 5010 这种独立视频端点**：它的控制台是通过 Foxglove 订阅 `/SLB_CAM_A|B|C/compressed`（每路 10Hz 的 CompressedImage）并用 Blob 显示的——也就是**D360S 的视频仍在大图走 WS**，正是我们在 D360 上刚消掉的队头阻塞形态。
- 所以"APP 只用一个视频端点"这条对 D360S **暂不成立**。要让两个产品共用同一份视频契约、并让 APP 只保留一条视频路径，需要给 D360S 也做一个等价端点（相机节点内嵌 H.264/MPEG-TS，端口与路径与 D360 对齐：同样 5010 + `/api/camera/preview.ts`），并把 D360S 控制台的三路订阅删掉。D360S 尚未发布，可以按工程规范直接改。
- 该项属于服务端任务，不在本 APP 交接范围内，但**它决定 APP 是否需要保留两条视频路径**，请优先决策。