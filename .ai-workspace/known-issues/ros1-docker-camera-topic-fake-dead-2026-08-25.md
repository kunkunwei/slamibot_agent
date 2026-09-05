# ROS1 + Docker：重启容器后 ROS 话题假死与相机无图快速排查

更新时间：2026-08-25
客户转发版：`.ai-workspace/procedures/customer-oak-camera-no-image-recovery-2026-08-25.md`
适用范围：Jetson、ROS1 Noetic、Docker、`core`/`firmware-sensors`/`scout-nav`。

## 一、典型现象

- APP、WEB 看不到 2D/3D 数据或视频；
- `rostopic info` 仍能看到 Publisher，但 `rostopic hz` 显示 `no new messages`；
- `rosnode list` 中节点时有时无；
- 容器状态为 `Up`，但容器内关键 ROS 子进程已经退出或卡死；
- 日志出现：
  - `X_LINK_ERROR`
  - `Communication exception`
  - `new node registered with same name`
  - `shutdown request ... Reason: new node registered with same name`
- MediaMTX 正常监听 8554，但 RTSP `/live` 返回 404。

## 二、底层机理

ROS1 节点启动后会向 ROS Master 注册节点、Publisher、Subscriber，并公布自己的 XML-RPC/TCP 地址。Docker 重启、强制停止或启动脚本管理不完整时，可能出现：

1. 节点进程异常退出，ROS Master 的注册信息短时间未清理；
2. 子进程未被 PID 1 正确回收，出现孤儿进程、残留连接或重复启动；
3. 新容器再次启动同名节点；
4. ROS Master 发现同名节点后，通常让新节点注册并通知旧节点退出，而不是永久拒绝新节点；
5. 如果旧节点残留、节点反复崩溃重启、或容器/宿主机连接到不同 ROS Master，就会表现为节点“假活着”、Topic 有注册但没有数据。

因此，`rostopic info` 中有 Publisher **不等于**该 Publisher 当前正在发布有效消息，必须结合 `rosnode ping`、进程和 `rostopic hz` 判断。

## 三、快速定位流程（只读优先）

### 1. 确认 ROS Master 一致

```bash
echo "$ROS_MASTER_URI"
docker exec firmware-sensors env | grep ROS_MASTER_URI
docker exec scout-nav env | grep ROS_MASTER_URI
```

确认宿主机和相关容器指向同一个 ROS Master，通常为：

```text
http://127.0.0.1:11311
```

### 2. 看节点、进程和连通性

```bash
rosnode list | grep -Ei 'oak|camera|stitch'
pgrep -af 'oak_hardware_trigger_ros|oak_keyframe_stitcher'
rosnode ping /oak_hardware_trigger_ros
rosnode ping /oak_keyframe_stitcher
```

判断：

| 现象 | 结论 |
|---|---|
| `rosnode list` 无节点，`pgrep` 无进程 | 节点未启动或已退出 |
| `rosnode list` 有节点，`pgrep` 无进程，`rosnode ping` 失败 | ROS Master 中存在残留注册 |
| 有进程且能 ping，但 Topic 无消息 | 节点活着但设备通信、触发或发布循环异常 |
| 同一节点出现多个进程/不断变化 PID | 存在重复启动或崩溃后反复拉起 |

### 3. 检查相机 Topic 是否真的有数据

```bash
for t in \
  /SLB_CAM_A/compressed \
  /SLB_CAM_B/compressed \
  /SLB_CAM_C/compressed
do
  echo "===== $t ====="
  rostopic info "$t"
  timeout 5 rostopic hz "$t"
done
```

重点看：

```text
Publishers: None
no new messages
```

如果 Publisher 存在但无频率，说明不能只根据注册信息判断相机正常。

### 4. 查看容器状态和子进程

```bash
docker ps

docker top firmware-sensors
docker logs --tail 300 firmware-sensors 2>&1 | \
  grep -Ei 'oak|camera|trigger|x_link|communication|error|exception|failed'
```

容器 `Up` 只代表容器主进程仍在，不代表 `oak_hardware_trigger_ros` 等子节点正常。

## 四、相机节点专用判断

`oak_hardware_trigger_ros` 是 OAK 相机的硬件触发 ROS 驱动，负责：

```text
OAK-FFC-4P
  -> oak_hardware_trigger_ros
  -> /SLB_CAM_A/B/C/compressed
  -> oak_keyframe_stitcher / 视频推流节点
```

出现以下日志时，应优先判断 OAK 设备通信异常，而不是先改 APP：

```text
Communication exception
Couldn't read data from stream: 'sysinfo' (X_LINK_ERROR)
Device likely crashed
```

这表示相机初始化可能成功过，但后续与设备的 USB/X-Link 通信断开、设备崩溃或设备配置异常。此时即使 ROS 节点名称仍在，也可能已经不再发布帧。

## 五、同名节点日志的解释

```text
shutdown request: [/oak_keyframe_stitcher]
Reason: new node registered with same name
```

这通常表示 ROS Master 发现新旧节点同名，并要求旧节点退出。它不必然表示“新节点注册失败”。需要进一步检查：

```bash
pgrep -af 'oak_hardware_trigger_ros|oak_keyframe_stitcher'
rosnode ping /oak_keyframe_stitcher
```

若节点反复出现同名关闭日志，重点查：

- 宿主机和容器是否同时启动同一节点；
- `firmware-sensors` 是否存在重复 roslaunch；
- 容器重启策略和启动脚本是否重复拉起子进程；
- 是否存在多个 ROS Master。

## 六、视频链路检查

### RTSP/MediaMTX

```bash
pgrep -af 'mediamtx|oak_rtsp_pusher|ffmpeg'
ss -lntup | grep -E ':(8554|8000|8001|8888|8889)\b'
timeout 8 ffprobe -v error -rtsp_transport udp \
  -show_entries stream=codec_name,width,height,r_frame_rate \
  -of default=nw=1 rtsp://127.0.0.1:8554/live
```

判断：

- 8554 未监听：MediaMTX 未启动；
- 8554 监听但 `/live` 返回 404：MediaMTX 没有推流者发布 `live`；
- 有 `oak_rtsp_pusher.py`/`ffmpeg` 且 ffprobe 能读到 H264：RTSP 链路基本正常；
- ROS 相机 Topic 无数据：优先修复相机源，不要先改 RTSP。

### APP/HTTP 视频接口

当前 APP 使用：

```text
http://<Jetson-IP>:5000/api/go2/stream/visible
```

检查：

```bash
curl -I --max-time 5 \
  http://127.0.0.1:5000/api/go2/stream/visible
curl -I --max-time 5 \
  http://127.0.0.1:5001/
```

需要区分：

- 5000 的接口返回 404：后端路由未实现或未注册；
- 5001 页面返回 200：页面服务正常，不代表视频源正常；
- ROS 相机 Topic 无数据时，5001、RTSP、APP 都可能无画面；
- HTTP 404 是接口问题，不能单独用来证明相机硬件故障。

## 七、推荐处理顺序

```text
1. 确认 ROS_MASTER_URI 一致
2. 确认是否有重复节点/重复 roslaunch
3. 检查 oak_hardware_trigger_ros 进程和 rosnode ping
4. 检查 /SLB_CAM_A/B/C/compressed 的 Publisher 与 hz
5. 结合 firmware-sensors 日志处理 X_LINK_ERROR
6. 相机 Topic 恢复后，再检查 oak_keyframe_stitcher
7. 再检查 oak_rtsp_pusher、ffmpeg、MediaMTX
8. 最后检查 5001 页面和 APP HTTP 视频接口
```

## 八、禁止的误判和操作

- 不要因为 `docker ps` 显示 `Up` 就认为所有 ROS 节点正常；
- 不要因为 `rostopic info` 显示 Publisher 就认为正在出图；
- 不要先修改 APP 或重建镜像来解决 `X_LINK_ERROR`；
- 不要直接删除 ROS Master、ROS 日志、地图或数据库；
- 不要把 APP 的 HTTP MJPEG 接口和 MediaMTX 的 RTSP 接口混为同一个服务；
- 先完成只读证据链，再执行容器重启、设备重置或节点重启。

## 九、最小现场记录模板

```text
时间：
ROS_MASTER_URI：
firmware-sensors 状态：
scout-nav 状态：
相机节点进程：
rosnode ping：
/SLB_CAM_A hz：
/SLB_CAM_B hz：
/SLB_CAM_C hz：
X_LINK_ERROR：有/无
重复节点日志：有/无
mediamtx/ffmpeg/pusher：
RTSP ffprobe：
5000 HTTP 接口：
5001 页面：
结论：
处理动作：
验证结果：
```


## 十、跨传感器依赖：MID-360 时间共享失活导致 OAK 硬触发无图

本地 `livox_ros_driver2` 源码确认了以下数据链：

```text
MID-360 有效点云包
  -> livox_ros_driver2 将设备 handle 映射到内部 index 并入队
  -> Lddc 处理有效点云包
  -> 创建并 mmap /dev/shm/timeshare
  -> 每个有效 PointCloud2/CustomMsg 包写入 pointt->low（雷达时间戳）
  -> oak_hardware_trigger_ros 等待并 mmap 同一 timeshare
  -> OAK 硬触发/时间同步采集
  -> /SLB_CAM_A/B/C/compressed
```

关键代码事实：

- `/dev/shm/timeshare` 只在 Livox 点云轮询首次进入时创建；
- 只有处理到非空、有效的 PointCloud2 或 Livox CustomMsg 包时，`pointt->low` 才更新；
- PCL 格式（`xfer_format=2`）明确不会更新时间共享；
- `Storage point data failed ... can not get index` 表示 SDK 收到的数据无法映射到已登记的雷达设备 index，数据不会进入正常发布链，因此雷达 Topic 与 timeshare 都可能停止更新。

因此，`timeshare` 文件存在、OAK 日志显示 `Timeshare ready`，只能证明文件可打开，不能证明雷达时间仍然活跃。必须读取文件内容多次，确认第二个 64 位整数持续变化。

当前客户现场若同时满足：5001 雷达不亮、`/livox/lidar` 无消息、timeshare 数值冻结、Livox 持续报 index/storage 错误、三路相机 Publisher 为 None，则优先判定为“雷达/时间同步上游先失活，OAK 硬触发链随后失效”。若雷达 Topic 和 timeshare 都持续更新，而相机仍无 Publisher 且出现 `X_LINK_ERROR`，则应判定为独立的 OAK USB/X-Link 故障，不能归因于雷达。

## 十一、2026-09-05 现场验证：驱动退出可单独恢复

已验证故障组合：A/B/C 无 Publisher；`/oak_hardware_trigger_ros` 为失效注册且 ping `connection refused`；容器内无对应真实进程；Livox、`/clock` 与 timeshare 仍健康。此时无需重启整个 `firmware-sensors`，确认无同名真实进程后，可按原 launch 参数单独启动驱动，A/B/C 与 `/keyframe` 恢复，现场 PASS。

边界：该手动进程不受 roslaunch 管理且退出后不自启；禁止在真实进程存在时重复启动。若出现持续 `X_LINK_ERROR` 或 USB reset/disconnect，应升级为容器恢复或完整断电/USB3链路检查，不能反复拉起。ROS 时间只认 `/clock`；互联网 NTP不作为本故障恢复条件。完整命令与验收见 `.ai-workspace/procedures/oak-camera-node-quick-recovery-2026-09-05.md`。
