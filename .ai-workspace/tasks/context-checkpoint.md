# Context Checkpoint — 开始作业 /keyframe 无视频

- 日期：2026-08-27 13:05–13:10 CST。
- 技术基线：ROS1 Noetic（CURRENT）；Jetson 已由用户确认开机。
- 用户现象：图传链路下 APP“开始作业”左下角无视频，并显示 rosbridge 未连接。
- 图传地址：Jetson `192.168.144.87`；APP 端 `192.168.144.11`；rosbridge `:9090`，API `:5000`。
- 实时证据：Jetson `eth2` 正常绑定 `192.168.144.87`；9090/5000 均监听 `0.0.0.0`。
- 9090 有两条来自 `192.168.144.11` 的 ESTABLISHED 连接；`/rosbridge_websocket` 存活且订阅 `/keyframe`。
- 直接故障：`/keyframe` 类型正确但 `Publishers: None`、无消息。
- 上游：A/B 相机约 10Hz，C 约 6.7Hz；`oak_hardware_trigger_ros` 存活。
- `oak_keyframe_stitcher` 未运行；当前 launch 日志显示启动后约 4.5 秒 `[KeyframeStitcher] interrupted`，随后 `signal_shutdown [atexit]`，exit code 0。
- `/use_sim_time=true`、`/clock` 约 200Hz；launch 无 respawn，因此退出后不恢复。
- 结论：无视频由 stitcher 退出导致；APP“rosbridge 未连接”与现场 ESTABLISHED/ROS 证据不符，是误导性状态显示。
- 远端动作：仅 SSH 只读检查；未启动节点、未重启/修改容器、未部署。
- 待用户授权：临时单独启动 stitcher，或实施 launch/节点正式修复并部署。
- 详细证据：`.ai-workspace/known-issues/oak-keyframe-stitcher-dies-in-roslaunch-2026-08-27.md`。
