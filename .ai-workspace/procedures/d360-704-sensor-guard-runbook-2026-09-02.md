# 704 D360 自动快速恢复 Runbook

状态：**轻量v3、旧连接清理和rosbridge心跳已部署；Hotspot/WiFi切换用户验收PASS**。

## 常态轻量检查

每30秒只读取SystemMonitor的小消息：`/topic_frequencies`末端`/livox/lidar`、`/keyframe`，以及`/driver_status`、`/project_duration`和真实进程。健康轮约5–6秒，不订阅大点云或A/B/C压缩图像。

## 异常深查与恢复

末端雷达异常时才读取point_num和`/dev/shm/timeshare`；keyframe异常时先读`/keyframe/header`，仍异常才检查A/B/C Publisher/header。确认故障且项目空闲后：stop-t20→inspect false/pid0→确认无真实残留→固定输入y执行ROS1 cleanup→start→验证Livox、timeshare、A/B/C、keyframe。标定/采集中只告警；180秒冷却；不kill/pkill；原`/led_control`灯语不变。

## Hotspot/WiFi与WebSocket

固定地址：Hotspot `192.168.117.6:9090/5001`；公司WiFi `192.168.31.219:9090/5001`。WiFi要求NTP=yes；Hotspot允许离线恢复。

已确认模式切换故障不是传感器：Livox10Hz、keyframe3–4Hz、5001 HTTP200、9090监听，但旧网段WebSocket保持ESTABLISHED并积压约1.93MB，导致新模式客户端“连接但无数据”。

根本修复：core容器内`project_control/launch/core.launch`的rosbridge include已设置：

```xml
<arg name="websocket_ping_interval" value="5" />
<arg name="websocket_ping_timeout" value="10" />
```

当前仅优雅重启rosbridge子进程加载；core容器、ROS Master、firmware-sensors容器的ID/StartedAt/PID未变化。旧会话在10秒内失效，新Hotspot连接`.208→.117.6:9090`建立且Send-Q=0；用户确认APP和WEB图像/雷达全部恢复。

辅助脚本`/usr/local/sbin/d360-clear-stale-clients`每轮只尝试处理本机已不再持有的旧9090/5001源IP；当前有效IP连接不动。rosbridge心跳是主要清理机制。

## 部署与验证

远端：

```text
/usr/local/sbin/d360-auto-recover
/usr/local/sbin/d360-quick-recover
/usr/local/sbin/d360-clear-stale-clients
/etc/systemd/system/d360-auto-recover.service
/etc/systemd/system/d360-auto-recover.timer
```

`d360-auto-recover.timer`每30秒，enabled/active。本地Shell语法PASS、147 tests PASS。传感器自动恢复和连接切换均已有现场闭环。

备份：`/home/jetson/d360-stale-client-fix-backup-1788411858`、`/home/jetson/rosbridge-heartbeat-backup-1788413094`。