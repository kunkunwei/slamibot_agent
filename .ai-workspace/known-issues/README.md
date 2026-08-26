# 已知问题（known-issues）

## 用途
记录历史踩坑，供后续 AI 与开发者参考。典型：Planner 超时、TF 问题、rosbridge 异常、
Docker 网络问题、Jetson 特定问题、ROS1/ROS2 差异。

## 格式
每个问题一个 `.md`，包含：现象、复现、根因、解决/规避、状态（open/resolved）、日期、相关仓库/栈。

## 规则
- 作为参考，不凌驾于当前事实源与代码状态。
- 新问题先记录再修复，避免重复踩坑。

## 索引
- [d360-handover-2026-08.md](./d360-handover-2026-08.md) —— D360 2D 导航交接文档汇总（导航坑 + 6 项未解决问题）
- [3d-nav-issues-2026-08.md](./3d-nav-issues-2026-08.md) —— 3D 导航问题汇总（自研 + 外协）
- [map-icon-direction.md](./map-icon-direction.md) —— 地图机器人图标方向不对
- [point-marking-ime-s.md](./point-marking-ime-s.md) —— 标记点位时英文输入法无法输入字母 s
- [web-app-map-display-2026-08-18.md](./web-app-map-display-2026-08-18.md) —— 历史根因报告；端口/IP 结论已被 2026-08-19 双 rosbridge 决策取代
- [map-record-cleanup-2026-08-19.md](./map-record-cleanup-2026-08-19.md) —— 前端无可用 2D 地图记录的清理、备份、隔离与遗留项
- [app-map-cbor-rosbridge-2026-08-19.md](./app-map-cbor-rosbridge-2026-08-19.md) —— 9090 rosbridge 的 CBOR `/map` live patch；未持久化且 APP UI 仍未显示
- [app-2d-map-quick-triage-2026-08-24.md](./app-2d-map-quick-triage-2026-08-24.md) —— APP/Web 无 2D 栅格地图的最小只读排查路径（优先读取）
- [scout-nav-process-reload-risk-2026-08-24.md](./scout-nav-process-reload-risk-2026-08-24.md) —— scout-nav 入口进程耦合、禁止直接重启/Uvicorn 退出及安全热测试路径
- [ros1-docker-camera-topic-fake-dead-2026-08-25.md](./ros1-docker-camera-topic-fake-dead-2026-08-25.md) —— OAK 相机无图、ROS Topic 假死、X_LINK_ERROR 与重复节点的快速排查；相机无图现象优先读取此文档，禁止先做大范围源码搜索。
- [robot-state-publisher-exits-scan-broken-2026-08-26.md](./robot-state-publisher-exits-scan-broken-2026-08-26.md) —— robot_state_publisher 未运行导致 /scan 断链、导航与 3D 定位全断（open，待重启导航栈验证）
- [robot-map-pose-no-publisher-2026-08-26.md](./robot-map-pose-no-publisher-2026-08-26.md) —— /robot_map_pose 无发布者：文档承诺后端转发从未实现，转发代码已部署待 /amcl_pose 生效
- [scout-base-flapping-after-reboot-2026-08-27.md](./scout-base-flapping-after-reboot-2026-08-27.md) —— 底盘激活重启后变 NONE：驱动注册但 /scout_status 零消息 → 8s 验证失败被终止 → 横跳；物理重启小车解决（硬件级状态异常）
- [oak-keyframe-stitcher-dies-in-roslaunch-2026-08-27.md](./oak-keyframe-stitcher-dies-in-roslaunch-2026-08-27.md) —— 开始作业无视频：install stitcher 二进制单独跑正常、只在 sensors.launch 上下文 4s 自杀；open 待查 launch 上下文差异
