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

## 2026-08-31 开机即无图复现

- Jetson 开机约 14 分钟时只读检查：A/B/C 分别约 10.04/10.00/9.96Hz，Livox 10.00Hz，`timeshare` 持续变化；风扇控制后的相机输入链正常，温度不能解释本次故障。
- 当前 run-id `2e5a95b6-1dd2-11b2-9774-00e09a2f15e6`：stitcher PID 55 成功订阅三路并创建 `/keyframe` Publisher，约 3.7 秒后 `[KeyframeStitcher] interrupted` → `signal_shutdown [atexit]`，roslaunch 判定 clean exit。
- 当前 `sensors.launch` 无 include，仅在第 45–50 行定义一次 stitcher；run-id 下也只有 PID 55 和 `oak_keyframe_stitcher-3.log`。未发现 `new node registered with same name`、第二 PID 或重复注册 shutdown，故“同名节点互相顶掉”假设未证实。
- 安装可执行文件是 aarch64 ELF/Cython 产物；容器无对应 source 工作树，现有日志只能确认正常返回路径，仍无法确定是谁触发 `interrupted`。
- 结论：开机即无图是 stitcher 在传感器 launch 启动后约 4 秒稳定退出造成；与相机过热是两条独立故障链。

## 2026-08-31 临时运行态恢复

- 经用户逐次授权，先启动默认实例验证，再仅 TERM 该临时 PID，并按 launch 原参数启动命名实例：`keyframe_hz=5.0`、JPEG quality 50、原 A/B/C Topic；未修改文件、launch 或持久 ROS 参数。
- 当前临时 PID 653，节点 `/oak_keyframe_stitcher`，已稳定观测至少 56 秒；`/keyframe` Publisher 已恢复。
- A/B/C 实测约 9.99/10.01/10.01Hz，原始相机帧率未下降。
- `/keyframe` 虽显式请求原配置 5.0Hz，实际仅约 3.96Hz；说明当前瓶颈不是参数被降频，后续需单独评估拼接/JPEG 处理吞吐。
- 该恢复仅为容器运行态，容器或 Jetson 重启后会丢失；开机 launch 约 4 秒退出的根因仍未修复。

## 2026-08-31 持久运行热修复部署

- tracked `src/device_service/launch/sensors.launch` 仅增加 `respawn="true" respawn_delay="3"`；A/B/C Topic、`keyframe_hz=5.0`、JPEG 50 均未变。
- 未执行约 40 分钟完整编译；以当前生产镜像 RepoDigest 为基线构建单层派生镜像，本地 `latest` 已切换到 `sha256:76b95d1e...`，未推 registry。
- 旧镜像保留为 `rollback-pre-keyframe-20260831-102133` → `sha256:71ff42d7...`；Compose 文件未修改，SHA256 仍为 `71be6a37...`。
- `firmware-sensors` 新容器 `f3544709...`，RestartCount=0；stitcher PID 54 独立验收时已稳定约 266 秒，无 respawn/storm，`/keyframe` Publisher 正常。
- 独立复核：A/B/C 约 10.00/10.00/10.09Hz，参数仍为 5.0/JPEG50，`/keyframe` 约 3.89Hz；未降低相机帧率。
- 该方案提供节点退出后的 roslaunch 自愈，但实际启动约 4 秒退出的触发源仍未定位；源码与 Dockerfile 尚未 Git commit/push，registry 也未推送。
