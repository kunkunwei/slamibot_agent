# Context Checkpoint — 简历材料已整理；本地读取器恢复；Jetson 已关机

- 日期：2026-08-30 CST；ROS1 Noetic（CURRENT）；Jetson `OFF_USER_CONFIRMED`，禁止 SSH。
- 本轮完成：依据 facts、tasks、known-issues、decisions 与周报，提炼 SLAMIBot 实习经历；未虚构未验收成果。
- 简历主线：D360 Scout Mini（Jetson Orin NX）ROS1 导航、Android/WEB、FastAPI、rosbridge、Docker 实机联调。
- 导航成果：重构/恢复 Docker 导航运行环境，定位 `/use_sim_time`、`/clock`、启动顺序与 `laser → base_link` TF 缺失导致的 `/scan`、AMCL/costmap 链路问题；稳定性仍有遗留，不写“彻底解决”。
- 地图成果：恢复 APP/WEB 2D 栅格地图；首帧 `1157×1071`、约 `0.05 m/pixel`；梳理 9090（客户端）/19090（FastAPI 内部）双 rosbridge；安全清理 5 条无效地图数据并校验 SQLite 完整性。
- 遥控成果：单变量 A/B 定位 `/global_cloud_navigation` 点云大流为图传网络控制延迟主因；关闭点云订阅后 RTT 约 `1099.28 ms → 36.0–41.5 ms`，RTO `2832 → 240–244 ms`，Send-Q 峰值 `8018 → 546`；保留 `/map` 与 25 Hz `/cmd_vel_web`。
- 视频成果：实现 `/SLB_CAM_B/compressed → FastAPI 最新帧缓存 → HTTP MJPEG → Android`，新增 `/api/camera/stream.mjpeg`；4 秒 32 帧、JPEG 边界完整、拍照 POST 200、RestartCount=0、真机 PASS；带宽约 22–23 Mbps 仍待优化。
- PCD 工具：面向约 4383 万点/1.4 GiB binary PCD，实现分块 box/polygon+Z 清障、dry-run、全套地图重建及防覆盖/删除比例保护；本地 `16 passed`，未真图部署。
- 语音成果：六麦阵列、sherpa-onnx、讯飞 gateway、TTS 与 APP 联调；“小飞小飞→我在”真机 PASS，后端 37 passed、唤醒定向 14 项 PASS；点位匹配/去抖等仍待优化。
- 工程化亮点：多仓库安全同步、事实源/任务审计/回滚机制与本地 AI 协作工作台；仅作为机器人业务后的次要亮点。
- 排除表述：未完成 ROS1→ROS2 迁移；Go2 WebRTC 未实施；AMCL/运动超调未完全验收；自动到点拍照 T1/T2 未完整 PASS；PCD 工具未上线。
- 本地读取器修复：`F:\my_story\.agents` ACL 所有权异常已恢复；13 个文件 SHA-256 一致；PowerShell、Node REPL、setup refresh `errors=[]`。
- 当前业务任务仍以 `.ai-workspace/tasks/current.md` 为准；照片手动功能已验收，自动到点 T1/T2 待 Jetson 开机后验证。
- 输出目标：向用户提供标准简历版、一页精简版、技术栈及面试介绍；公司名、岗位名、时间使用占位符。
- 工作区逻辑压缩已完成；运行时无独立底层 compaction 工具可调用。
