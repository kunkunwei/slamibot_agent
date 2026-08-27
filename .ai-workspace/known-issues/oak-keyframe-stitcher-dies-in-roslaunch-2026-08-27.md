# OAK keyframe stitcher 在 roslaunch 上下文 4s 自杀：开始作业无视频

- 日期：2026-08-27
- 状态：open（未解决，需后续专项排查）
- 相关：`firmware-sensors` 容器、`sensors.launch`、`ros1_oak_ffc_sync/oak_keyframe_stitcher`、开始作业 `/keyframe` 视频
- 技术栈：ROS1（CURRENT）

## 背景澄清
- 「开始作业」的视频 = `/keyframe`（`sensor_msgs/CompressedImage`，OAK 3 相机横向拼接），由 `oak_keyframe_stitcher` 发布，**不是** go2 图传。
- go2 图传 `/api/go2/stream/visible` 只对应「导航控制」新增的 ▣ 视频按钮（独立进程，见 `go2-video-stream-architecture`）。
- APP `NativeDataCollectionSession.kt:131` 订阅 `/keyframe`。

## 现象
- 开始作业无视频；APP 该页显示「rosbridge 未连接」（实际 rosbridge 9090 握手正常，`/keyframe` 被 rosbridge 订阅但无发布者）。
- `/keyframe`：`Publishers: None`；`/SLB_CAM_A/B/C/compressed` 三路相机 10Hz 正常。
- `oak_keyframe_stitcher` 进程不在（sensors.launch 无 respawn → 进程退出后不拉起）。

## 关键实验证据
1. **install 二进制单独跑完全正常**：`docker exec firmware-sensors ... oak_keyframe_stitcher __name:=oak_keyframe_stitcher_diag` + `timeout 25` —— 订阅三路相机、宣布发布 `/keyframe`、**存活满 25s**（EXIT_CODE=124 = timeout 杀的），证明二进制本身无自杀缺陷。
2. **只在 sensors.launch 上下文自杀**：启动约 4s 后 `[KeyframeStitcher] interrupted`（exit code 0），日志时间戳落在容器启动时段；source/install 两份 `sensors.launch` **字节一致**，均无 respawn。
3. **模拟时间已启用**：`/use_sim_time=true`、`/clock` 200Hz。手动跑时日志显示 sim time 1776211359（≈2026-04-15，比 wall 早 133 天，by design）。
4. 相机过热（OAK 100°C）曾导致三路无帧；降温至 78°C 后相机恢复 10Hz，但 **stitcher 仍未恢复**（降温柔和后没重新拉起，因为无 respawn）。

## 未定论
- roslaunch 上下文里谁在 ~4s 时触发 shutdown：可能是 sim-time 交互（`rospy.Rate` 在 sim time 下等 /clock）、master/参数竞争、或 launch 内其它节点影响。**未抓到 shutdown reason**。
- 「出图了」需与 go2 图传区分：开始作业 `/keyframe` 目前确认**仍未发布**。

## 下一步建议（待授权/另开会话）
1. 复现时在容器抓 stitcher 完整日志（`rostopic`/`rosout`），拿到 `signal_shutdown` 的 reason。
2. 对比 `docker exec` 直接跑 vs `roslaunch sensors.launch` 的环境差异（sim-time、node 名、`__log`、rosmaster 连接）。
3. 短期规避：sensors.launch 给 stitcher 加 `respawn="true"`（业务代码，需授权）。
4. 或按用户选择的方案 A 结论推进：已证明二进制健康，焦点收敛到 launch 上下文的环境差异。

## 2026-08-27 13:05 CST 图传链路现场复核

- Jetson `eth2` 正常绑定 `192.168.144.87/24`；9090、5000 均监听 `0.0.0.0`。
- `ss` 显示两条 `192.168.144.11 -> 192.168.144.87:9090` ESTABLISHED 连接。
- `/rosbridge_websocket`、`/scout_nav_rosbridge` 存活；前者已订阅 `/keyframe`。
- `/keyframe` 类型为 `sensor_msgs/CompressedImage`，但 `Publishers: None`，6 秒内无消息。
- A/B 相机约 10Hz，C 约 6.7Hz；相机发布节点存活，stitcher 进程不存在。
- 当前 launch 日志精确记录：stitcher 成功启动后约 4.5 秒输出 `[KeyframeStitcher] interrupted`，随后 `signal_shutdown [atexit]`；roslaunch 判定 `process has finished cleanly`，exit code 0。
- `/use_sim_time=true`，`/clock` 约 200Hz；launch 仍无 respawn。
- 结论：APP 无视频的直接原因是 `/keyframe` 生产者退出；“rosbridge 未连接”不是网络事实，而是 APP 状态呈现问题。
- 本次仅 SSH 只读采证，未启动节点、重启容器或修改远端文件。
