# D360 704 自动快速恢复

状态：**轻量v3已部署；30秒timer active；Hotspot/WiFi均启用**。

## 轻量常态检查

每轮只读取小消息：`/topic_frequencies`中的末端`/livox/lidar`和`/keyframe`、`/driver_status`、`/project_duration`以及真实进程。健康轮约5–6秒，不订阅点云或三路压缩图像。

只有末端异常才深查：Livox point_num、`/dev/shm/timeshare`、`/keyframe/header`，必要时A/B/C Publisher/header。确认故障且项目空闲后执行stop20→inspect→无残留进程→ROS cleanup→start→完整验收。标定/采集中只告警；180秒冷却；不kill/pkill；不改原LED灯语。

网络契约：Hotspot `192.168.117.6:9090/5001`；公司WiFi `192.168.31.219:9090/5001`。WiFi要求NTP=yes；Hotspot允许离线恢复。传感器健康但APP连不上时转查地址缓存/WebSocket，不恢复传感器。

部署：`/usr/local/sbin/d360-auto-recover`、`/usr/local/sbin/d360-quick-recover`，`d360-auto-recover.timer` enabled/active。v2备份：`/home/jetson/d360-lightweight-v3-backup-2968`。

验证：Shell语法PASS，本地139 tests PASS；远端连续两轮约5–6秒，均为`lidar=10.0/10.1Hz keyframe=4.0Hz status=11`，容器ID/StartedAt/PID未变。