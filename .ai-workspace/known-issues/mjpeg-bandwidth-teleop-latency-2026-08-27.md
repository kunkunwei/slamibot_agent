# MJPEG 视频流占用带宽导致遥控延迟

- 日期：2026-08-27
- 状态：OPEN / optimization_pending
- 技术栈：ROS1 Noetic；HTTP MJPEG。

## 已确认链路

```text
OAK 相机
→ ROS1 /SLB_CAM_B/compressed
→ FastAPI 最新 JPEG 缓存
→ HTTP MJPEG /api/camera/stream.mjpeg
→ Android APP / 浏览器
```

- 源头是 ROS compressed image Topic，APP 接收的是 HTTP MJPEG。
- 不是 RTSP、WebRTC、RTMP 或 WebSocket 视频。
- 后端复用拍照已有的最新帧缓存，不新增 ROS 订阅、不保存视频队列、当前不缩放也不重编码。

## 现象与数据

- 用户真机确认：实时视频和拍照功能正常。
- 开启实时视频后，摇杆控制小车延迟明显增大。
- 默认约 8 FPS；单帧约 355 KB；4 秒约 11.4 MB；估算带宽约 22–23 Mbps。
- MJPEG 每帧都是完整 JPEG，缺少 H.264 一类帧间压缩。
- 视频与 rosbridge、地图/点云、遥控命令共享链路，容易造成队列积压、重传及控制包延迟。

## 优化方向与优先级

1. **优先降低 MJPEG 帧率**：导航预览先从约 8 FPS 降到约 4 FPS，预计带宽近似减半至约 11–12 Mbps。改动最小，基本不增加 Jetson CPU，也不改变 ROS Topic。
2. **降低源 JPEG 码率**：先核对 OAK 发布配置、分辨率、JPEG quality 和 `/SLB_CAM_B/compressed` 的其他消费者，再决定是否调整；禁止未经核对直接修改相机参数。
3. **后端缩放或重编码**：可只为 APP 输出低分辨率/低质量 JPEG，网络更省，但会增加 Jetson CPU 占用，并改变当前“直接复用 JPEG”的实现。
4. **长期协议升级**：若需要更高帧率和更低带宽，评估 H.264/RTSP 或 WebRTC，同时修改服务端和 APP；不得假设当前 OAK 或容器已经提供 RTSP。
5. **联调指标**：优化时同时观察视频吞吐、摇杆指令延迟/Send-Q、rosbridge 稳定性、地图/点云刷新以及 Jetson CPU，避免只看画面流畅度。

## 当前决定

- 只记录问题与优化方向，尚未实施带宽优化。
- 未修改 ROS Topic、OAK 参数、APP 协议或 Jetson 运行态。
- 推荐下一步：经用户授权后先实施并真机验证约 4 FPS 的最小方案。

## 2026-08-27 `/keyframe` 现场核验

- Jetson/core：`/keyframe` 类型为 `sensor_msgs/CompressedImage`，但 `Publishers: None`，8 秒内无新消息；当前不能作为导航实时视频源。
- `/keyframe` 当前订阅者包括 `/system_monitor` 与 `/rosbridge_websocket`，但无发布端。
- 当前源 `/SLB_CAM_B/compressed` 由 `/oak_hardware_trigger_ros` 发布，约 10 FPS、单帧约 0.35 MB、ROS Topic 带宽约 3.69 MB/s（约 29.5 Mbps）。HTTP MJPEG 再限为约 8 FPS，所以 APP 实测约 22–23 Mbps。
- APP 数据采集模块已有 `/keyframe` 的 `sensor_msgs/CompressedImage` 订阅代码，但导航模块当前使用独立 HTTP MJPEG；不能据此认为 `/keyframe` 现场可用。
- rosbridge JSON 传输压缩图像通常需要 Base64，等尺寸 JPEG 会增加约三分之一负载；若与控制共用 9090，还会把大图像引入 rosbridge/控制链路。即便另开 WebSocket，也只隔离单连接队头阻塞，不降低无线总带宽。
- 结论：当前不切到 `/keyframe`。优先保留 5000 HTTP MJPEG 与 9090 控制分离，并把 MJPEG 降至约 3–4 FPS。只有将来确认 `/keyframe` 恢复发布且帧率/单帧显著更低时，才评估独立 WebSocket 的低带宽预览模式。
