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

---

## 10. 服务端补充与勘误（2026-09-19，复核 APP 侧 AI 的计划后追加）

### 10.1 交接文档的两处遗漏（我认账，本文档为准）
- **`RtkService.kt` 是第 4 个 rosbridge 客户端**（§3 表里漏了）：它自带一套 rosbridge JSON 实现（`connectRosbridge`、订阅 `/rtk/gga`、`advertise` + 发布 `/rtk/rtcm`、`call_service /rtk/login` 与 `/rtk_stop`）。切到 Foxglove 后整套替换，且 `/rtk/rtcm` 属**客户端发布**，必须按 `ros1` 编码序列化 `std_msgs/UInt8MultiArray`。
  - 服务端方向已核实（`src/device_service/src/ntrip_rtk_ros_service.py`）：设备**发布** `rtk/gga`（`std_msgs/String`，NMEA）、**订阅** `/rtk/rtcm`（`std_msgs/UInt8MultiArray`）；设备模式时设备自己也会发布 `/rtk/rtcm`。→ APP 手机模式推 RTCM 到 `/rtk/rtcm` 是对的。
- §6/§7 里"删除按 `/keyframe` 取值的代码""验收 `/topic_frequencies`"这两条**只针对 5001 控制台，不针对 APP**（APP 全仓没有消费 `/topic_frequencies`）。APP 侧按自己的实际代码判断。

### 10.2 客户端发布（`/cmd_vel_web`、`/rtk/rtcm`、`/gimbal/pry_cmd`）的精确契约
- 已读 ROS1 桥源码（`ros1_foxglove_bridge_nodelet.cpp::clientAdvertise`）：**只接受 `encoding == "ros1"`**，其它编码直接抛 `ClientChannelError`。
- 桥侧解析客户端 advertise 时**只要四个键**：`id`、`topic`、`encoding`、`schemaName`（`websocket_server.hpp` 的解析里没有 `schema`/`schemaEncoding`）——**类型是桥拿 `schemaName` 去 ROS master 查出来的**，不需要客户端传 `.msg` 文本。所以 APP 计划里的 `schemaEncoding:"ros1msg"` + `.msg` 文本**不必要**（传了也无害）。
- `topic` 仍需过桥的 client topic 白名单（默认 `.*`，未配置限制）。
- 风险仍成立：真机要确认一次 `/rtk/rtcm` 上行被桥接受并到达设备（走 `ros_babel_fish` 反序列化 + master 取类型）。

### 10.3 服务响应的形状
- 确认：Foxglove 的服务响应是**响应消息本身（扁平 JSON）**，没有 rosbridge 的 `values` 包装。APP 现有 `optJSONObject("values") ?: response` 的写法能兼容两种。
- 建议：真机抓一条 `/get_version` 样本存档后，**把 `?: response` 兼容分支删掉**（只留新形状），符合"不留兼容层"。

### 10.4 一条容易误判的验收细节
- ROS1 桥**会为没有发布者的话题也 advertise 通道**（0.8.4 起）。所以"订阅成功/有通道"≠"有数据"；真机验收要看**数据有没有到**（例如 `/global_cloud_navigation`、`/map` 的空闲态本来就没有帧）。

### 10.5 `setGimbalAngles` 的 `/gimbal/pry_cmd` 是死发布
- D360 固件仓 `src/` 下**没有任何云台节点**（只有 device_service / faster-lio / lidar_add_rgb / livox_ros_driver2 / oak-camera_driver），全仓对 `gimbal`/`pry_cmd` 零命中 → 该发布没有任何订阅者。建议在 APP 侧直接删除（与"不留死代码"一致）。

---

## 11. §9 的跨产品缺口：**2026-09-19 已解决**（服务端补齐，APP 保持单一路径）

- D360S 仓（gitee `electech6/SLAMIBOT_D360_Framework`，分支 `codex/d360s-foxglove-cbor`，commit **`f732eb4`**）已补上与 D360 **完全等价**的端点：
  `http://<host>:5010/api/camera/preview.ts`（`Content-Type: video/mp2t`）、状态 `…/preview.ts/status`；
  相机节点（`src/oak_cam_ros2/scripts/oak_hardware_trigger_ros2.py`）内嵌 ffmpeg/x264，参数与 D360 一致（`preview_enable/preview_port/preview_path/preview_fps/preview_scale/preview_cam_order`），HHTP 头、8 客户端上限、1MB 有界队列、空闲不编码、0→1 重建进程、退出重启一次——全部与 D360 同款。
  `install.bash` 的 `APT_PACKAGES` 已加 `ffmpeg`；`runtime.bash` 进程白名单已放行 `ffmpeg`。
- D360S 控制台（`ota_server/web_page`）已从"订阅三路 `/SLB_CAM_*/compressed` 画 canvas"改成"`<video>` 播这一条流"（vendored `mpegts.min.js` 与 D360 是**同一个 git blob** `8870135…`）；三路 `CompressedImage` 的**发布仍在**（`lidar_add_rgb` 点云着色与 `SystemMonitor` 的 Hz 上报还在用）。
- **因此 APP 只需保留一条视频路径**：两个产品都是 `:5010/api/camera/preview.ts`。不要为 D360S 加任何回退/第二条路径。
- 未验证：5010 在 D360S 上是否与其它进程冲突（离线不可判）；`preview_cam_order` 默认 `CAM_B,CAM_A,CAM_C` 是否与 D360S 物理装法一致（真机看画面，必要时用 `--ros-args -p preview_cam_order:=…` 临时改）；x264 在 D360S 上的 CPU。---

## 12. 给批次 3/4/5 的服务端补充（2026-09-19，主代理复核批次 2 后新核实）

### 12.1 ⚠️ RTK 停止服务名：设备是 `rtk/stop`，不是 `/rtk_stop`
- 设备侧（D360 ROS1 `src/device_service/src/ntrip_rtk_ros_service.py`）：`rospy.Service('rtk/login', …)`（:272）与 `rospy.Service('rtk/stop', …)`（:273）。**全仓没有 `rtk_stop`**。
- APP 当前 `RtkService.kt:447` 处理的是 `"/rtk_stop"` → 批次 5 必须改成 `rtk/stop`（否则停止指令永远打不中服务）。

### 12.2 ⚠️ D360S 上没有 2D 导航话题，也没有底盘运动链路（产品分档，不是 bug）
- 在 D360S 仓（`SLAMIBOT_D360_Framework_ros2`）全仓 grep：`/map`、`/global_cloud_navigation`、`/robot_map_pose` **零命中**；`cmd_vel`/`scout`/`ugv`/`CAN` 运动链路 **零命中**。
- 结论：D360S（基础款＝3D 空间重建）不发布 2D 地图/导航点云/AMCL 位姿，也没有 `/cmd_vel` 消费者；`/cmd_vel_web` 的真正终点在 D360 的**导航加装包**（nav_api teleop → `/cmd_vel` → scout_base）。
- 因此 APP 侧必须**按能力门控**（"存在才用"）：D360S 上隐藏/禁用导航与摇杆相关 UI，**不要**写回退或兼容分支。这不是兼容层要求，是产品分层要求。

### 12.3 点云话题名：不要写死 `/point_cloud`
- D360S 的点云来自 Faster-LIO 与其着色链；本轮我没能在 `src/faster-lio` 里定位到话题常量（目录布局与预期不同），**以设备 `ros2 topic list` 为准**。工作台既有观测记录里 D360S 看到 `/Odometry` 与 `/cloud_registered`（约 4.93Hz）。
- 建议批次 3 落地时：把"采集款点云话题"按设备实际 advertise 的通道做**存在性选择**，而不是硬编码 `/point_cloud`；真机联调第一步就是 `ros2 topic list | grep -i cloud`。

### 12.4 批次 4（ExoPlayer）的关键参数
- URL 两产品一致：`http://<host>:5010/api/camera/preview.ts`；响应头是 `Content-Type: video/mp2t`、**无 Content-Length、`Connection: close`**、`Cache-Control: no-store`。
- 服务端 `-g = fps`（1 秒一个 IDR）+ 周期 PAT/PMT → **从 GOP 中途接入 ≤1s 出画**。
- ExoPlayer：`MediaItem` + `MimeTypes.VIDEO_MP2T`（URL 以 `.ts` 结尾也会被推断为 TS）+ `setLiveConfiguration`（把 target offset 压到 1–3s 降延迟）+ `setVideoTextureView`（保持现有自绘布局，不用 media3-ui 的 PlayerView）。
- **不要**给 D360S 加第二条视频路径：D360S 已于 `f732eb4` 补上同一端点（见本文档 §11）。

### 12.5 批次 5 的命名问题
- 设备 `/health` 返回的 `rosbridgeConnected` 是**服务端字段名**（nav_api 内部 19090 roslibpy 的连接状态），**不要改**；但 UI 上那个 "ROSBridge" 文案应改成用户能懂的（如"导航后端"）——文案属 APP 侧。

### 12.6 关于既有失败用例（G20）
- 该失败在干净 HEAD 上可复现，是**陈旧断言**（历史记录：全量单测 63/64，唯一失败即 G20 摇杆旧期望）。**不要**在本链路批次里顺手改它（会把"链路回归"和"测试对齐"混在一起）；单独开一个小任务对齐即可。