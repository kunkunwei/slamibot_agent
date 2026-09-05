# 704 D360 OAK/Livox 标定诊断手册

> **2026-09-05 更正声明（必须先读）**：原 NTP 前后恢复仅是历史相关性观测，不能定为因果。通用恢复应检查 `/use_sim_time`、`/clock` 连续性、timeshare/数据健康，不要求互联网 NTP。本文保留历史数据；其中规范性“必须 NTP yes”仅作为不再适用的历史实验步骤，禁止误执行。


更新时间：2026-09-02
适用边界：设备 704、D360、ROS1 Noetic；仅 `core`、`firmware-sensors`、`ota_web`。用途是 3D 空间重建、测绘与标定；无导航内容，不套用 scout-nav 或 ROS2。

## 1. 安全级别

- **A（只读、可自动执行）**：`ping`、`ip`、`nmcli -f`、`docker inspect/ps/top/logs`、`rosnode`、`rostopic`、`rosparam get`、`od/stat/ps`、端口查询、容器内解码。不得改变运行态。本次已通过 wlan0 `192.168.31.219` 执行用户授权的只读 SSH 诊断。
- **B（可逆修复，需确认）**：证据保全后 `docker restart firmware-sensors` 或明确的 stop/start。会中断传感器，执行前确认窗口并保存现场输出；本次未执行。
- **C（持久网络、断电，需单独确认）**：NetworkManager profile 修改、网卡启停、线缆/供电调整、设备断电；本次未执行。当前不建议修改已正确的 eth1 profile。
- A 级 SSH 仅限只读诊断；未经单独授权不得执行 B/C 或任何远端写入。密码和密钥不记录。

## 2. 704 当前结论

**历史观测（因果未确认，底层机制 UNKNOWN）**：STM32 连接 MID360，并经 CH341 USB 串口向 Jetson 传输/校验数据；不兼容的 STM32 固件与雷达数据校验/封装异常存在相关性，但不能据此确定因果。Jetson 侧表现为 96 点、约 2083Hz 的 UDP 包级 ROS 消息及长时间停流，Faster-LIO 收到碎片后出现 Too few 和巨量漂移。Livox 驱动是异常表现承接层，不是本次已确认首要根因。

旧周期 11:42 的节点存活但 pointcloud 无新消息、timeshare 冻结，以及 11:49 后的 96点/2083Hz，均保留为对照。2.0.6 在 NTP 首次同步前仍复现该异常；确认 `NTPSynchronized=yes` 后仅重启同一传感器容器即恢复健康，因此只能记录为启动时序/时间基准与恢复结果的历史相关性，因果未确认；Livox 更底层切换机制仍 UNKNOWN。`mapping_avia` 仍是独立配置风险，需在健康基线下静止复测判断。

## 3. 一键只读采集前置

**宿主机执行**的标准 ROS 命令先加载：
```bash
source /opt/ros/noetic/setup.bash
```
**容器内执行**必须使用完整命令，避免与宿主机 Docker 命令混用：
```bash
docker exec -i firmware-sensors bash -lc 'source /opt/ros/noetic/setup.bash; source /root/SLAMIBOT_D360_Framework/install/setup.bash; command'
```
正常结果：命令可找到并使用正确 ROS1 环境。异常结果：`timeout: failed to run command 'rostopic'`，结论是未 source 的 ENV 错误，下一步先 source 再重试。`/oak_hardware_trigger_ros` 是节点不是 Topic；`rostopic logs` 不存在；Docker stdout 无输出不代表 ROS 文件日志无日志。

## 4. 设备、容器与时钟判定

```bash
hostname; date -Is; docker ps --format 'table {{.Names}}\t{{.Status}}'
docker inspect -f 'StartedAt={{.State.StartedAt}} RestartCount={{.RestartCount}}' core firmware-sensors ota_web
```
正常结果：三容器均运行，`RestartCount` 不持续增加。异常结果：容器退出或重启计数增加。结论：先记录容器状态再进入对应分支。Docker `StartedAt/Up 56 years` 是系统早期时钟为 1970、后跳到 2026 造成，不能用该显示判断真实运行时长；以进程启动时间、日志时间和连续采样为准。下一步执行真实进程判定。

## 5. 节点与真实进程

```bash
rosnode ping -c 3 /livox_lidar_publisher2
rosnode ping -c 3 /oak_hardware_trigger_ros
rosnode ping -c 3 /oak_keyframe_stitcher
docker top firmware-sensors | grep -Ei 'livox|oak|stitcher'
```
正常结果：ping 有 XML-RPC reply，`docker top` 有对应真实进程。异常结果：仅 `rosnode list` 有名字、ping 失败或无真实进程。结论：名称/容器 Up 不是数据健康证明。下一步分别查 OAK 和 Livox 数据。

## 6. OAK 分支（A 只读）

```bash
for t in /SLB_CAM_A/compressed /SLB_CAM_B/compressed /SLB_CAM_C/compressed; do
  timeout 5 rostopic hz "$t"
  timeout 5 rostopic bw "$t"
  timeout 5 rostopic echo -n 3 "$t/header"
done
timeout 5 rostopic hz /keyframe
timeout 5 rostopic echo -n 1 /keyframe/header
```
正常结果：A/B/C 约 10Hz，每帧约 0.41/0.26/0.33MB，seq/stamp 递增；`/keyframe` 约 3.6Hz、5760x1200。异常结果：无新消息、header 冻结或 `/keyframe` 无数据。结论：频率、带宽和 header 同时健康才算采集链健康。下一步执行无文件直接解码。

设备内执行（不写文件，依赖已安装的 `rospy`、OpenCV、NumPy）：
```bash
docker exec -i firmware-sensors bash -lc 'source /opt/ros/noetic/setup.bash; source /root/SLAMIBOT_D360_Framework/install/setup.bash; python3 -' <<'PY'
import cv2, numpy as np, rospy
from sensor_msgs.msg import CompressedImage
rospy.init_node('oak_decode_readonly', anonymous=True, disable_signals=True)
topics = ['/SLB_CAM_A/compressed','/SLB_CAM_B/compressed','/SLB_CAM_C/compressed']
for topic in topics + ['/keyframe']:
    try:
        msg = rospy.wait_for_message(topic, CompressedImage, timeout=5.0)
        raw = np.frombuffer(msg.data, dtype=np.uint8)
        image = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
        if image is None: print(topic, 'decode=FAIL', 'bytes=', len(msg.data)); continue
        print(topic, 'bytes=', len(msg.data), 'shape=', image.shape, 'mean=', float(image.mean()), 'std=', float(image.std()), 'min=', int(image.min()), 'max=', int(image.max()))
    except Exception as e: print(topic, 'ERROR', str(e))
for topic in topics + ['/keyframe']:
    try:
        a = rospy.wait_for_message(topic, CompressedImage, timeout=5.0)
        t0 = rospy.Time.now(); rospy.sleep(0.6)
        b = rospy.wait_for_message(topic, CompressedImage, timeout=5.0)
        dt = (b.header.stamp - a.header.stamp).to_sec() or (rospy.Time.now()-t0).to_sec()
        ia = cv2.imdecode(np.frombuffer(a.data, np.uint8), cv2.IMREAD_GRAYSCALE)
        ib = cv2.imdecode(np.frombuffer(b.data, np.uint8), cv2.IMREAD_GRAYSCALE)
        diff = cv2.absdiff(ia, ib)
        print(topic, 'dt=', dt, 'mean_absdiff=', float(diff.mean()), 'changed_pct=', float((diff > 2).mean()*100.0))
    except Exception as e: print(topic, 'DIFF_ERROR', str(e))
PY
```
正常结果：三路约 1920x1200，灰度均值约 108–121、std 约 60–77、min=0/max=255；间隔约 0.6 秒的 `dt` 有效且像素变化约 12–23%。异常结果：超时、解码失败、黑帧、空包或 `changed_pct` 接近 0。结论：现场证据表明 OAK 采集、压缩、时间戳、stitcher 正常；否则按 OAK-XLink/OAK-CONTENT 分支。下一步若 ROS 数据健康但标定页无图，转 WEB-DISPLAY。

宿主机执行：
```bash
rosnode ping -c1 /rosbridge_websocket
rosnode info /rosbridge_websocket
rostopic echo -n1 /client_count
ss -lnt | grep -E ':9090|:5001'
```
正常结果：rosbridge ping 成功，`rosnode info` 可核对 keyframe 订阅，`/client_count` 有值（现场为 1），9090 与 5001 监听。异常结果：节点不可达、无 keyframe 订阅、client_count 无消息或端口未监听。结论：ROS 数据和 rosbridge 正常但页面无图时，根因转浏览器/传输/前端解码渲染/缓存，不再归因相机硬件。下一步查 WEB-DISPLAY。

## 7. Livox 分支（A 只读）

宿主机执行（先 `source /opt/ros/noetic/setup.bash`）：
```bash
rostopic info /livox/lidar/pointcloud
timeout 8 rostopic hz /livox/lidar/pointcloud
timeout 8 rostopic echo -n1 --noarr /livox/lidar/pointcloud
```
容器内执行（CustomMsg 类型需要同时 source install）：
```bash
docker exec -i firmware-sensors bash -lc 'source /opt/ros/noetic/setup.bash; source /root/SLAMIBOT_D360_Framework/install/setup.bash; rostopic info /livox/lidar; timeout 8 rostopic hz /livox/lidar; rostopic echo -n5 /livox/lidar/point_num'
```
正常结果：用于本机 Faster-LIO 采集时，`/livox/lidar` 应稳定约 10Hz、每条 CustomMsg 约 20064 点，IMU 约 200Hz，且不得出现长时间 `no new messages`。异常结果：当前现场实测为包级约 2083Hz、`point_num=96`，或 Publisher None、空数组、频率突发后长停。结论：2083Hz/96点不是健康值，而是 UDP 包级数据被错误暴露为 ROS 扫描帧；宿主机缺 `livox_ros_driver2/CustomMsg` 仅表示未 source install。下一步采样 timeshare、参数、配置、网卡与 UDP。

```bash
docker exec firmware-sensors sh -lc 'for i in $(seq 1 10); do date +%T.%3N; od -An -td8 -N16 /dev/shm/timeshare; sleep .5; done'
rosparam get /xfer_format
docker exec firmware-sensors sh -lc "ps -eo pid,lstart,etime,args | grep -E 'livox|oak' | grep -v grep"
```
正常结果：第二个 int64 每 0.5 秒增长，`xfer_format=1`，进程持续。异常结果：文件不存在或第二个值冻结。结论：冻结表示有效点云/时间共享链卡死；文件存在、mmap ready 不能证明健康。下一步保全日志与网络证据。

宿主机执行，默认先看计数器/邻居/端口：
```bash
ip -s link show eth0
ip neigh show 192.168.1.101
ss -lunp | grep -E '56000|56101|56201|56301|56401'
```
正常结果：eth0 收发计数在两次采样间增长、邻居可见、五个 UDP 端口已绑定。异常结果：计数不变、邻居不可见或端口未绑定。结论：进入 NET-ETH0 或 LIVOX-NODATA。下一步保全证据；若工具存在且已有抓包权限，可选执行 `timeout 5 tcpdump -ni eth0 'udp port 56000 or udp port 56101 or udp port 56201 or udp port 56301 or udp port 56401'`，不是无条件 A 命令。

宿主机执行日志检查：
```bash
docker logs --since 15m firmware-sensors 2>&1 | grep -Ei 'livox|storage|index|timeshare|error|failed|exception'
docker exec firmware-sensors bash -lc 'find /root/.ros/log -maxdepth 2 -type f -printf "%p\\n" 2>/dev/null | sort'
```
正常结果：可取得当前周期 Docker/ROS 文件日志；异常结果：Docker 无相关输出或找不到文件。结论：现场 Livox C++ `__log` 路径虽被传入但文件未生成，现有文件只有 roslaunch/OAK 日志，无法确认底层触发；SDK 未重连等仍是候选。下一步记录结果后按决策树，不先重启。

## 8. eth0/eth1 专项

```bash
nmcli -f connection.id,connection.interface-name,ipv4.method,ipv4.addresses,connection.autoconnect connection show
ip -br addr; cat /sys/class/net/eth0/carrier; cat /sys/class/net/eth1/carrier
ip -s link show eth1; nmcli device status
```
正常结果：eth0 `192.168.1.55/24`、carrier=1、up，profile `eth0-radar` manual/autoconnect；MID360 host `192.168.1.55`、雷达 `192.168.1.101`。eth1 carrier=0、down、无 IPv4、零收发，但持久 profile `eth1-radar` manual/autoconnect，地址已是 `192.168.144.55/24`。结论：eth1 固定地址已完成，缺的是物理链路/对端；eth1 不是 MID360 数据口，绝不能改成 `192.168.1.55` 形成双网口同 IP/同子网。无链路不要 `nmcli con up` 伪装修复。下一步按业务是否确实需要 eth1 分 NET-ETH1-BUSINESS，否则保持不动。

授权后才可修改的示例（当前 profile 正确，本次不执行）：先在工单中直接复制保存 `nmcli -f connection.id,connection.interface-name,ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.never-default,connection.autoconnect con show eth1-radar` 的原值；不强制写 `/tmp`。若未来 profile 存在但地址错误，且已单独获得 C 级授权：
```bash
nmcli con mod eth1-radar ipv4.method manual ipv4.addresses 192.168.144.55/24 ipv4.gateway '' ipv4.never-default yes connection.interface-name eth1 connection.autoconnect yes
# 只有 carrier=1 时才执行：
nmcli con up eth1-radar
```
正常结果：profile 字段正确，且有物理 carrier 时连接成功。异常结果：无 carrier、连接失败或路由异常。结论：无链路不执行 `nmcli con up`；当前无需修复。下一步若需回滚，使用改前记录的原值逐字段 `nmcli con mod` 恢复，再按授权执行连接操作。

## 9. 开始采集后箭头与点云持续漂移

### 9.1 采集前硬门槛（宿主机只读）

现场装机资料的健康基线是 `/livox/lidar` 约 10Hz、`/livox/imu` 约 200Hz；Livox 连接 STM32，STM32 经 CH341 `/dev/ttySTM32`（实际 `/dev/ttyUSB1`）传输/校验数据。

```bash
source /opt/ros/noetic/setup.bash
for t in /livox/lidar /livox/imu; do timeout 30 rostopic hz "$t"; done
for i in $(seq 1 6); do docker exec firmware-sensors sh -lc 'od -An -td8 -N16 /dev/shm/timeshare'; sleep 5; done
```
正常结果：连续 30 秒 `/livox/lidar` 约 10Hz、每条 `point_num` 约 20000，`/livox/imu` 约 200Hz且无 `no new messages`，timeshare持续增长；2.0.4 后现场已 PASS。异常结果：频率不达标、空包/停顿或timeshare冻结。结论：任一项失败都禁止开始采集。下一步先诊断 STM32/链路，不重复烧录或重启硬顶。

### 9.2 项目启动与数据箭头（宿主机/容器边界明确）

```bash
# 宿主机：核对服务类型与当前项目日志，不执行启动
source /opt/ros/noetic/setup.bash
rosservice type /project_control
rosservice args /project_control
rosnode list | grep -E 'laserMapping|run_mapping_online|lidar_add_rgb'
```
正常结果：类型为 `project_control/Base`，请求仅 `string params`；日志中的项目名为 `704_1_A/start_device`，随后记录“录制已启动”“SLAM已启动”。异常结果：类型/请求不符或节点缺失。结论：不能照抄项目名操作；先从日志确认项目。下一步仅在另行授权时使用已确认的 stop 请求。

当前链路：`laserMapping` 订阅 `/livox/lidar`、`/livox/imu`，发布 `/Odometry`、`/cloud_registered_body`；`lidar_add_rgb` 订阅两者，发布 `/slam_pose`（`nav_msgs/Odometry`）与 `/point_cloud`。箭头和点云一起移动因此是同一上游 Faster-LIO 里程计发散，不是 APP 对点云重复应用 pose。

### 9.3 开始后 10 秒止损（宿主机只读）

```bash
source /opt/ros/noetic/setup.bash
for t in /Odometry /slam_pose /point_cloud; do timeout 10 rostopic hz "$t"; done
# 先从当前项目日志/进程确认项目名，以下 PROJECT 仅替换为已确认值，不得盲抄
PROJECT='已从当前日志确认的项目名'
find "/etc/slamibot/project_log/latest/$PROJECT" -maxdepth 1 -type f -name 'out_slam_*.log' -print
for f in /etc/slamibot/project_log/latest/$PROJECT/out_slam_*.log; do
  [ -f "$f" ] && grep -Ei 'Too few points|Too few input point cloud' "$f"
done
```
正常结果：静止时 `/Odometry`、`/slam_pose` 约 10Hz，位移近零，mapping 日志无持续 Too few。异常结果：频率稀疏、位移/箭头快速漂移或日志持续 `Too few points, skip this scan`、`Too few input point cloud`。结论：日志重定向在项目目录，不从 firmware-sensors Docker stdout 判断；项目名必须先确认。下一步立即 stop_device，不重启硬顶并保全证据。

已确认异常样本（烧录前对照）：静止 20 秒仅 39 个 `slam_pose`、8 个 IMU 样本；pose header 跨度 11.438532s，净位移 29028.964464m、累计 29303.892523m，yaw 变化 54.437716°，XYZ 范围 6866.985/2309.678/28153.495m，坐标约 (-9万,10万,-39万) 继续发散，但 twist speed 仍为 0。IMU 稀疏；当时不能仅凭巨漂认定 STM32/IMU 刷错，后续 A/B 证据已确认 STM32 固件不兼容。

### 9.4 点云粒度与配置风险（只读）

```bash
source /opt/ros/noetic/setup.bash
rosparam get /xfer_format
rosparam get /common
rosparam get /preprocess
rosparam get /mapping
# 容器内：核对实际运行 launch/yaml 文件（只读）
docker exec firmware-sensors bash -lc 'source /opt/ros/noetic/setup.bash; source /root/SLAMIBOT_D360_Framework/install/setup.bash; find /root/SLAMIBOT_D360_Framework -type f \( -name "mapping_avia.launch" -o -name "avia.yaml" \) -print'
```
正常结果：`/common`、`/preprocess`、`/mapping` 有实际参数，运行 launch/yaml 可定位。异常结果：命名空间为空或文件与运行进程不符。结论：现场 `/laserMapping` 为空，不能用它判断配置；必须以实际全局命名空间和运行文件为准。下一步继续核对输入粒度及日志。
正常结果：完整扫描约 20064 点、publish_freq=10，`/Odometry`/`/cloud_registered`约10Hz；2.0.6在NTP同步后重启传感器已达到该基线。异常结果（NTP同步前）：单条仅14–31点、downsamp 5/10 后有效点2–8，日志 Too few。结论：latest 镜像在时间基准未稳定时曾把一条96点 UDP 包作为约2083Hz包级消息，Faster-LIO收到碎片；该现象与 STM32 固定启动计时、系统墙钟后续 NTP 同步同时出现，属于历史相关性观测；启动时序竞态的因果关系未确认，不再归因固件版本或 Livox 驱动单变量。`mapping_avia.launch` + `avia.yaml`（scan_line=6、blind=4、Avia外参）仍是独立配置风险，需健康基线下静止复测。下一步以 `/use_sim_time`、`/clock` 连续性、timeshare/数据健康及 10Hz/约20000点和静止漂移验收配置。

工作台旧案例正常实测为 CustomMsg 每帧约20064点、publish_freq=10、Odometry/cloud_registered约10Hz，并记录过同一路径驱动版本差异风险。当前 latest 镜像 id 仅记录为 `sha256:71ff42...`，Livox binary SHA 为 `02a59b6...`；旧 v1.0/v1.1 不含该 D360 Livox/Faster-LIO 安装路径，不能直接回退，截断 hash 不扩写。

### 9.5 点数据间歇停止与安全停机

宿主机只读（CustomMsg 的 `point_num` 必须在容器内执行）：
```bash
source /opt/ros/noetic/setup.bash
timeout 25 rostopic hz /livox/lidar
ip -s link show eth0; ip neigh show 192.168.1.101
docker exec firmware-sensors bash -lc 'source /opt/ros/noetic/setup.bash; source /root/SLAMIBOT_D360_Framework/install/setup.bash; timeout 12 rostopic echo -n 100 /livox/lidar/point_num'
```
正常结果（2.0.4后）：持续约10Hz、非空点数据；异常结果（烧录前）：25秒可0消息，或12秒窗口约第8秒突发40条后继续 no new messages。同步15秒 eth0仅每秒约3个小状态包（约583 bytes），不是持续点数据；carrier=1且无USB reset。结论：该异常与STM32不兼容固件导致的校验/封装异常一致，Livox驱动是承接层；下一步异常时证据保全并 stop，恢复后不要重复烧录。

已确认 stop 请求（本次服务返回 `Device already stopped`，不是本次执行修复）：
```bash
docker exec core bash -lc 'source /opt/ros/noetic/setup.bash; source /root/SLAMIBOT_D360_Framework/install/setup.bash; rosservice call /project_control "params: '\''704_1_A/stop_device'\''"'
```
正常结果：服务确认停止，`project_duration=0`，无 rosbag/laserMapping/lidar_add_rgb，`/slam_pose` 为 None、`/point_cloud` 不存在。异常结果：仍有采集节点或服务错误。结论：先从日志/进程确认项目名，不能照抄删除其他项目。下一步关闭 APP/页面后重开；不要把缓存显示当后台仍采集。

当前后端已停止，但 rosbridge `client_count=2`，一条9090连接 Send-Q约1.1MB；用户仍看到移动是 APP/浏览器继续消费缓存/队列或 UI 状态未清空。完全关闭 APP/页面后重开；必要时另行授权重启 core/断开 rosbridge，本次未执行。

### 9.6 STM32 固件与启动时序诊断（当前结论已修正）

硬件拓扑：MID360 连接 STM32，STM32 经 CH341 USB 串口向 Jetson 传输/校验；`/dev/ttySTM32 -> /dev/ttyUSB1`，CH341 `1a86:7523`，RTK 为 ttyUSB0，不能混用。2.0.4 的 UART2 GPRMC checksum 修复、固定日期150426和启动计时是源码事实；UART1 COG 用于版本诊断，UART2 发给雷达 COG 固定180。STM32不联网同步时间。

2.0.4 文件 size=29300、SHA256=`86a61413d77854b3573b0a84c9e6d3af7a4ae330fbff6a347a5cc6bbf96a7efe`；日志证明13:20:39自动降级烧录，13:21:21成功并启动。当前用户更新至2.0.6，GPRMC COG=206；文件 `/etc/slamibot/firmware_uploads/19700101_080058_slb_d360_stm32_2.0.6.bin` size=29816、SHA256=`16f94107e88949255b9c24925a404f8c45d26e363b7205ebeb36c614ecb6007b`。本地源码仓库没有2.0.6源码/bin，来源与可回滚性 UNKNOWN；暂留但不扩散，不来回刷。

2.0.6 在 NTP 首次同步前仍是稳定约2083.434Hz、point_num=96、IMU约200Hz；说明单纯换固件未修复聚合。系统证据：Livox 14:44启动，timesyncd 14:45:07才首次NTP同步；ROS/Livox header最终与wall一致，但 STM32 GPRMC仍为启动计时001257、固定日期150426。15:02:50确认 `NTPSynchronized=yes` 后，仅重启一次 `firmware-sensors`，同一2.0.6与同一Livox二进制恢复：30秒lidar 242条、有效24.072秒、10.011Hz，point_num主值19968/20064；IMU 199.863Hz；timeshare增长；OAK约9.9–10Hz、keyframe约3.67Hz。结论：传感器早于 NTP 同步启动与随后恢复存在历史相关性，但因果未确认；启动时序/时间基准竞态；Livox SDK如何因时间变化切换聚合仍 UNKNOWN。

### 9.7 已完成固件烧录的复用边界（未来 C 级）

当前无需执行。未来必须先停项目并确认 project_duration=0、无 rosbag/laserMapping/lidar_add_rgb，检查文件 `stat`/`sha256sum`、串口别名和 COG，保持供电/USB稳定且60秒不拔线；优先 ROS 服务 `/stm32/firmware_update`，禁止直接 `api_update()`（默认 ttyUSB0 会误碰 RTK且绕过暂停监听）。成功须见暂停监听→9600 YMODEM→恢复监听→success；失败不连续重试或断电。COG=206为2.0.6，`/get_version`=1.0.15是设备软件版本。

LED 源码结论：2.0.4/317 启动 `ws2812_Init` 全灭、`g_led_state active=0`；默认灯灭不等于固件损坏，未知命令不要乱发。协议模板仅记录不建议执行：`rgbcontrol:<mode>:<times>:<r>:<g>:<b>:<checksum>`；源码 checksum 校验被注释，times=0可能除零，未知命令可能 reset。USART1 不显式 NUL 结束、YMODEM CRC16/大小上限/IROM与IAP地址仍为代码风险，不擅自修。

## 10. 当前处置结论

当前后端已停止，传感器在NTP同步后重启并通过10/200Hz预检；先完全关闭 APP/页面重开清缓存，再新建短测试项目执行静止10秒止损和60秒漂移验收，未通过前禁止正式采集。不再来回刷STM32，也不在NTP未同步时靠重启硬顶。若 D360 重启，不得把 `timedatectl ...=yes` 当作通用恢复门槛；应先检查 `/use_sim_time`、`/clock` 连续性及 timeshare/数据健康。永久修复方向 UNKNOWN；不得把“等待 NTP yes 后启动”作为规范性方案，任何 systemd/compose/entrypoint 改动需另行授权；当前不提供可误执行的写文件命令。

## 11. 单向根因决策树

1. 未 source 或命令找不到？→ **ENV**：只补 source，回到 4。
2. 时钟异常且只依赖 Docker 年龄？→ **CLOCK**：以进程/连续采样判定，回到 4。
3. 节点名有但无真实进程？→ **ROS-STALE**：记录后进入授权恢复，不清理即当修复。
4. OAK hz/header/解码异常？X-Link/设备异常→ **OAK-XLink**；解码黑/空/重复→ **OAK-CONTENT**；上游健康但 keyframe 异常→ **STITCHER**。
5. Livox 无数据？UDP/邻居/eth0 异常→ **NET-ETH0**；网络正常且 raw 无数据→ **LIVOX-NODATA**；raw 有而 timeshare 冻结→ **LIVOX-TIMESHARE**。
6. eth1 无 carrier但 profile 正确？→ **NET-ETH1-BUSINESS**，查物理对端，不改地址。
7. ROS 与 rosbridge 有数据但页面无图？→ **WEB-DISPLAY**。每一步只进入一个分支，修复后回到全量复验。

## 12. 授权后的修复与复验

仅在项目已停止并完成证据保全、且已检查 `/use_sim_time`、`/clock` 连续性及 timeshare/数据健康后，才可另行授权重启 `firmware-sensors`；本轮 15:02:50 的一次重启已 PASS。当前 704 后端处于停止状态，不应重复烧录或把历史 NTP 时序实验当作通用恢复条件。

任何后续驱动或镜像修复后，必须复验 `/livox/lidar` 稳定约10Hz且每条约20064点、`/livox/imu`约200Hz、timeshare持续增长、`/Odometry`与`/slam_pose`静止不漂移、mapping日志无持续Too few，再验证三路OAK、`/keyframe`和rosbridge。不要因Docker stdout空白判定无日志；应检查项目mapping日志与ROS文件日志。

## 13. 成功标准与现场记录

成功：三容器稳定；真实 Livox/OAK 进程存在；raw/PointCloud2 内容持续；timeshare 增长；三路 OAK 约 10Hz、keyframe 约 3.6Hz且画面变化；rosbridge 可订阅；标定页显示正常。

记录模板：时间/设备/命令与 source；容器 StartedAt、RestartCount、进程 PID；eth0/eth1 carrier、地址、邻居、UDP；Livox hz、字段、timeshare；OAK hz/bw/header/解码统计；keyframe；rosbridge/client；日志摘要；根因代码；是否获 B/C 授权；复验结果。密码、密钥不记录。
