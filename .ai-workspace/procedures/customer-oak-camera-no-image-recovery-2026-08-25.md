# D360 客户现场：Jetson 重启后 OAK 相机无图恢复手册

更新时间：2026-08-25  
适用环境：Jetson、ROS1 Noetic、Docker、OAK-FFC 相机、`firmware-sensors` 容器。  
适用链路：ROS 图像 Topic；本手册不涉及 RTSP、MediaMTX 或 8554 端口。

## 1. 故障现象

Jetson 重启后，业务界面看不到相机图像。现场可能同时出现：

- `rosnode list` 仍能看到 `/oak_hardware_trigger_ros`；
- `rosnode ping /oak_hardware_trigger_ros` 返回 `connection refused`；
- 实际进程中没有 `oak_hardware_trigger_ros`；
- `/oak_keyframe_stitcher` 仍然存活，但没有有效上游图像；
- 日志可能出现 `Communication exception`、`X_LINK_ERROR` 或 `Device likely crashed`。

## 2. 原因说明

本次现象至少包含两类路径，必须先判断雷达同步链是否健康：

1. **雷达同步链中断**：当前代码中 Livox 点云处理负责创建并持续更新 `/dev/shm/timeshare`；`oak_hardware_trigger_ros` 启动相机前会等待并读取该共享时间戳。雷达节点、点云数据或时间戳更新停止后，文件可能仍存在、相机节点也可能仍可 `rosnode ping`，但相机硬件触发/发布链路可能随之失效。
2. **相机驱动异常退出**：`oak_hardware_trigger_ros` 负责连接 OAK 相机，并发布 `/SLB_CAM_A/B/C/compressed`。当 OAK USB/X-Link 通信异常时，该节点可能崩溃或退出。
3. **ROS Master 残留注册**：节点异常退出后，ROS Master 可能暂时保留旧节点名称和地址，所以 `rosnode list` 看似有节点，但 `rosnode ping` 无法连接。这属于失效注册，不代表节点仍正常运行。

注意：`rosnode cleanup` 只能清除失效注册，不能修复 OAK 硬件通信，也不会自动重新启动相机驱动。必须在清理后重新启动传感器容器并验证图像频率。

## 3. 先确认雷达 → timeshare → 相机依赖链

若 5001 监控中雷达不亮，或日志出现 `Storage point data failed`，优先执行以下只读检查，不要先重启容器：

```bash
source /opt/ros/noetic/setup.bash

rosnode list | grep -Ei 'livox|lidar'
rostopic list | grep -Ei 'livox|lidar|point'
docker top firmware-sensors | grep -Ei 'livox|lidar|oak|camera'
```

找到实际 Livox 节点和点云 Topic 后执行：

```bash
rosnode ping -c 3 /实际Livox节点名
rostopic info /实际雷达点云Topic
timeout 8 rostopic hz /实际雷达点云Topic
```

再检查共享时间戳是否持续变化：

```bash
for i in $(seq 1 10); do
  date +%T.%3N
  docker exec firmware-sensors od -An -td8 -N16 /dev/shm/timeshare
  sleep 1
done
```

判断：

- 雷达 Topic 无 Publisher/无消息，且 timeshare 数值不变化：先恢复 Livox 雷达链路；相机无图很可能是下游结果。
- 雷达 Topic 正常且 timeshare 持续变化，但 OAK Topic 无消息并报 `X_LINK_ERROR`：再转向 OAK USB/X-Link、供电、FFC 和设备配置。
- 不能仅凭 `/dev/shm/timeshare` 文件存在或日志出现 `mmap ok` 判定同步正常；mmap 内容必须持续变化。

## 4. 快速确认

在 Jetson SSH 终端执行：

```bash
source /opt/ros/noetic/setup.bash

rosnode list | grep -E 'oak|camera'
rosnode ping /oak_hardware_trigger_ros
rosnode ping /oak_keyframe_stitcher

docker top firmware-sensors | \
  grep -E 'oak_hardware_trigger_ros|oak_keyframe_stitcher'
```

符合以下组合时，可以判断存在残留注册：

```text
rosnode list 中存在 /oak_hardware_trigger_ros
+ rosnode ping 返回 connection refused
+ docker top 中没有 oak_hardware_trigger_ros 真实进程
```

## 5. 安全恢复流程

为避免直接重启过程中无法确认旧进程和旧注册状态，建议采用：

```text
停止容器 → 确认真正停止 → 清理失效注册 → 启动容器 → 验证
```

### 5.1 停止传感器容器

```bash
docker stop -t 20 firmware-sensors
```

确认容器真正停止：

```bash
docker inspect -f \
  'running={{.State.Running}} pid={{.State.Pid}} status={{.State.Status}}' \
  firmware-sensors
```

正常应显示：

```text
running=false pid=0 status=exited
```

检查宿主机是否还有相机相关进程：

```bash
pgrep -af 'oak_hardware_trigger_ros|oak_keyframe_stitcher'
```

正常应无输出。如果仍有输出，请记录完整内容，不要直接结束进程，先确认它由宿主机还是其他容器启动。

### 5.2 清理 ROS Master 失效注册

先确认 ROS Master 正常：

```bash
rosnode list >/dev/null && echo 'ROS Master 正常'
```

执行：

```bash
rosnode cleanup
```

出现确认提示时输入：

```text
y
```

此操作只清理无法连接的 ROS 节点注册，不删除代码、配置或数据。

### 5.3 重新启动传感器容器

```bash
docker start firmware-sensors
sleep 20
```

确认容器没有反复重启：

```bash
docker ps --filter name=firmware-sensors

docker inspect -f \
  'running={{.State.Running}} restarting={{.State.Restarting}} status={{.State.Status}}' \
  firmware-sensors
```

### 5.4 验证真实进程和节点

```bash
docker top firmware-sensors | \
  grep -E 'oak_hardware_trigger_ros|oak_keyframe_stitcher'

rosnode ping /oak_hardware_trigger_ros
rosnode ping /oak_keyframe_stitcher
```

健康状态应同时满足：

- `docker top` 能看到两个真实进程；
- 两个 `rosnode ping` 均持续返回 `xmlrpc reply`；
- 节点 PID 不反复变化。

## 6. 验证三路相机数据

```bash
timeout 5 rostopic hz /SLB_CAM_A/compressed
timeout 5 rostopic hz /SLB_CAM_B/compressed
timeout 5 rostopic hz /SLB_CAM_C/compressed
```

三路均能输出有效频率，说明 OAK 相机采集和 ROS 压缩图像发布已经恢复。

不能只看 `rostopic info` 中是否有 Publisher；必须以 `rostopic hz` 是否持续收到新消息为准。

## 7. 使用 MobaXterm 查看图像

### 7.1 确认 X11 转发

MobaXterm 中应启用 X Server，并在 SSH Session 的 `Advanced SSH settings` 中勾选 `X11-Forwarding`。

连接后执行：

```bash
echo "$DISPLAY"
```

正常会显示类似：

```text
localhost:10.0
```

如果输出为空，需要启用 X11 转发后重新连接 SSH。

### 7.2 使用 rqt_image_view 查看

```bash
source /opt/ros/noetic/setup.bash
rqt_image_view
```

在窗口的 Topic 下拉框中依次选择：

```text
/SLB_CAM_A/compressed
/SLB_CAM_B/compressed
/SLB_CAM_C/compressed
```

也可以直接打开一路：

```bash
rosrun rqt_image_view rqt_image_view /SLB_CAM_A/compressed
```

若压缩 Topic 无法直接显示，执行：

```bash
rosrun image_view image_view \
  image:=/SLB_CAM_A \
  _image_transport:=compressed
```

查看其他相机时，将 `A` 替换为 `B` 或 `C`。

X11 远程画面可能存在延迟，只用于确认画面内容是否正常，不用于评价实际视频链路延迟。

## 8. 如果节点再次退出

立即提取最近日志：

```bash
docker logs --since 5m firmware-sensors 2>&1 | \
  grep -Ei 'oak|camera|trigger|x_link|communication|error|exception|failed|crashed|device'
```

如果再次出现：

```text
Communication exception
Couldn't read data from stream: 'sysinfo' (X_LINK_ERROR)
Device likely crashed
```

说明问题已经不是单纯的 ROS 残留注册，而是 OAK USB/X-Link 通信没有恢复。处理方法：

1. 正常关闭 Jetson；
2. Jetson、BOX/OAK 相机全部断电；
3. 等待约 10 秒；
4. 检查 OAK 排线、USB连接和供电；
5. 重新上电；
6. 再验证进程、`rosnode ping` 和三路 Topic 频率。

如果 OAK/BOX 使用独立供电，仅重启 Jetson 系统可能无法复位相机，必须确保相机设备也真正断电。

## 9. 恢复成功标准

必须同时满足：

- `firmware-sensors` 容器稳定处于 `Up`；
- `docker top` 中存在 `oak_hardware_trigger_ros` 和 `oak_keyframe_stitcher`；
- 两个节点均可被 `rosnode ping`；
- `/SLB_CAM_A/B/C/compressed` 均有持续频率；
- MobaXterm 的 `rqt_image_view` 能看到正常图像。

只满足“容器 Up”或“节点名称存在”，不能判定相机已经恢复。

## 10. `ping` 成功但 Publisher 为 None 的判断

如果出现：

```text
/oak_hardware_trigger_ros 可以 rosnode ping
/SLB_CAM_A/B/C/compressed 的 Publishers 全部为 None
三路 rostopic hz 全部 no new messages
日志出现 X_LINK_ERROR
```

这不是 ROS Master 残留注册。节点的 ROS/XML-RPC 外壳仍存活，但 OAK 设备初始化或数据管线已经失败，因此没有创建或维持图像 Publisher。

如果初始化信息同时显示：

```text
Connected cameras:
cameraData: []
```

说明 OAK-FFC-4P 主设备被识别，但没有检测到实际相机模组，应优先检查 OAK/BOX 供电、USB链路、FFC排线和相机模组连接。

此时不应继续重复 `rosnode cleanup`。应完整关闭 Jetson，并让 Jetson 与 BOX/OAK 全部断电约10至20秒，检查连接后重新上电。若 OAK 有独立供电，仅重启 Jetson 或重启容器不能完成设备复位。

## 11. 本次现场结果（更新）

本次曾短暂观察到三路 Topic 有数据，并通过 MobaXterm X11 显示图像；随后三路 Publisher 全部变为 `None`，日志确认 `X_LINK_ERROR`，且设备信息显示 `cameraData: []`、`Connected cameras` 为空。

最新判断：5001 监控同时观察到雷达熄灭，结合 Livox 点云路径负责更新 `/dev/shm/timeshare` 的源码证据，应先验证“Livox 点云是否持续发布、timeshare 是否持续变化”。只有雷达同步链健康而 OAK 仍报错时，才将 OAK USB/X-Link 或相机模组连接/供电视为首要根因。当前尚未达到稳定恢复标准。


## 12. 雷达与相机的启动/同步依赖检查

D360 的相机硬触发依赖 Livox 驱动写入 `/dev/shm/timeshare`。文件“存在”不等于同步正常；必须确认其中的雷达时间戳持续变化。

只读检查顺序：

```bash
# 1. 找到雷达节点并验证真实点云
rosnode list | grep -Ei 'livox|lidar'
rosnode ping -c 3 /livox_lidar_publisher2
rostopic info /livox/lidar
timeout 8 rostopic hz /livox/lidar

# 2. 在传感器容器的 IPC/共享内存环境中读取 timeshare
# 16 字节结构为两个 int64；当前驱动持续更新第二个值（low）。
docker exec firmware-sensors sh -lc '
  stat -c "size=%s inode=%i mtime=%y" /dev/shm/timeshare
  i=0
  while [ "$i" -lt 12 ]; do
    date "+%H:%M:%S.%3N"
    od -An -t d8 -N16 /dev/shm/timeshare
    sleep 0.5
    i=$((i+1))
  done
'

# 3. 确认传输格式；0/1 会更新时间共享，2 不会
rosparam get /xfer_format

# 4. 核对雷达、相机真实进程及启动时间
docker exec firmware-sensors sh -lc \
  "ps -eo pid,lstart,etime,args | grep -E 'livox|oak_hardware_trigger_ros|oak_keyframe_stitcher' | grep -v grep"

docker inspect -f \
  'StartedAt={{.State.StartedAt}} RestartCount={{.RestartCount}} IpcMode={{.HostConfig.IpcMode}}' \
  firmware-sensors

# 5. 按 Docker 时间戳关联故障先后
docker logs -t --since 15m firmware-sensors 2>&1 | \
  grep -Ei 'livox|storage point|timeshare|oak|x_link|communication|error|failed'
```

判定：

- 雷达节点有注册但 `/livox/lidar` 无频率，且 timeshare 第二个数值不变：雷达进程虽然存活，但有效数据/时间同步链已经失活；
- timeshare 文件不存在：当前 IPC 环境中的 Livox 点云轮询从未成功进入；
- timeshare 存在但数值冻结：可能是历史文件或雷达有效包停止，不能把 `Timeshare ready` 当成健康；
- `/livox/lidar` 有稳定频率且 timeshare 数值持续变化，而三路图像无 Publisher：转查 OAK/X-Link，不归因于雷达；
- 日志先出现 Livox storage/index 错误和点云停止，后出现相机失图：支持雷达/同步上游先故障；
- 日志先出现 `X_LINK_ERROR`，同时雷达 Topic 与 timeshare 仍正常：支持 OAK 独立故障。


## 12. 已确认案例：Livox进程存在但未发布

现场确认组合：

- `/livox_lidar_publisher2` 可见，容器内也有真实进程；
- `/livox/lidar` 的 `Publishers: None`；
- 容器内 `/dev/shm/timeshare` 不存在；
- OAK和拼接进程仍存在，但图像Topic无Publisher。

该组合说明Livox进程只是启动了，尚未收到并处理首包有效点云；因为 `timeshare` 只在首次有效点云处理路径中创建，所以相机依赖的共享时间戳源不存在。应先查MID360配置、雷达网口链路、设备IP可达性和Livox当前启动日志，不应先清理ROS注册或处理APP。宿主机执行 `rostopic hz /livox/lidar` 若提示无法加载 `CustomMsg`，属于宿主机未source Livox消息环境；但 `rostopic info` 已显示 `Publishers: None` 时，仍可确认当前没有发布者。

## 13. 修正：不要把启动期 GetIndex 错误直接等同于雷达持续掉线

若日志顺序为：

```text
Storage/GetIndex failed
Update lidar succ
found a new lidar
GetFreeIndex / storage queue
timeshare ready
OAK mmap ok
OAK X_LINK_ERROR
```

则前段 `GetIndex` 错误至少可能是设备完成注册前已收到数据的启动竞态；后续 `timeshare ready` 证明该日志时段内Livox曾进入有效点云处理。若OAK在此之后仍显示 `cameraData: []`、`Connected cameras:` 为空并报 `X_LINK_ERROR`，不能将该次OAK失败直接归因于timeshare缺失。

如果当前检查又显示 `/livox/lidar Publishers: None` 且 `timeshare` 不存在，应先确认是否读取了不同启动周期的混合日志，并检查当前进程启动时间、网络绑定和UDP流量。双网卡配置相同IP/相同子网属于高风险网络歧义，必须先只读验证，未经授权不得直接删除地址或关闭网卡。

## 14. 已确认案例：eth1误配为雷达网段

正确规划为：

- `eth0 = 192.168.1.55/24`，专用于MID360雷达 `192.168.1.101`；
- `eth1 = 192.168.144.55/24`，用于另一条业务链路。

若eth0、eth1同时配置 `192.168.1.55/24`，会形成同IP同子网的双直连路由，可能造成Livox SDK UDP绑定、ARP应答和回包接口歧义。恢复时先确认SSH不经过eth1，再临时修正eth1，验证通过后按NetworkManager或netplan实际配置做持久化；不得修改eth0。网络修正后，Livox/OAK进程需要在正确地址环境中重新初始化，并分别验证雷达Topic、timeshare和三路相机Topic。

## 15. 雷达恢复但OAK Publisher无帧

若受控重启后出现：

- `/livox/lidar` 约10Hz；
- `/dev/shm/timeshare` 的low字段持续增长；
- 三路相机Topic均注册了 `/oak_hardware_trigger_ros` Publisher；
- 三路 `rostopic hz` 均持续 `no new messages`；

则雷达和共享时间戳上游已恢复，当前相机故障应独立定位到OAK/DepthAI设备、USB/X-Link、相机模组或采集循环。此时不要再处理Livox、ROS残留或timeshare；只读取当前启动周期OAK日志、USB枚举和内核USB事件。

## 16. OAK先以USB3启动，随后崩溃并回落Bootloader

本次内核日志确认了更精确的故障顺序：

1. OAK以`03e7:f63b Luxonis Device`在Bus02成功枚举为`SuperSpeed Gen 1`；
2. DepthAI成功识别CAM_A、CAM_B、CAM_C三颗AR0234，创建三路Publisher并启动Pipeline；
3. 数秒后出现`Disable of device-initiated U1/U2 failed`、USB reset/disconnect和`sysinfo X_LINK_ERROR`；
4. 设备随后以`03e7:f63c Luxonis Bootloader`重新出现在Bus01，只显示`480M`；
5. `oak_hardware_trigger_ros`退出，Master仅保留connection refused的失效注册。

因此，故障后的`lsusb -t`显示480M只是设备崩溃后回落到Bootloader/USB2伴随总线的结果，不能据此断言设备从未连接USB3。三颗相机模组已经被DepthAI识别，FFC缺失也不是当前首要假设。首要怀疑应调整为USB3信号质量、USB数据线、Hub/端口、供电或OAK设备/固件运行稳定性。

恢复优先级：完整断电复位；更换可靠的USB3数据线；绕过Hub直接连接Jetson USB3端口；检查Hub与OAK供电。重新上电时用`dmesg -w`观察`03e7:f63b`是否能持续保持SuperSpeed，并确认Pipeline运行后不再disconnect。若更换线缆、端口并完整断电后仍稳定复现同一时序，再进入DepthAI版本、设备固件和Pipeline配置兼容性调查。
