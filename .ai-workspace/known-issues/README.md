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
