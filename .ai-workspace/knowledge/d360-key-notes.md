# D360 关键技术与踩坑笔记（来自同事文档 2026-08）

> 跨三个导航项目共用的关键技术。来源：`同事文档/WebRTC，虚拟MAC地址，ROS1与ROS2的通信，关于导航时间戳，关于Claude Code在D360中的使用.md`

## 1. WebRTC（Unitree Go2 运动控制）
- 库：`unitree_webrtc_connect`（PyPI），源码 github.com/legion1581/unitree_webrtc_connect
- 安装：`sudo apt install -y python3-pip portaudio19-dev && pip install unitree_webrtc_connect`
- 测试脚本：`test_new.py` + `webrtc_sport_client.py`（绿联云 /volume1/实习生/D360/WebRTC 或设备 /home/jetson/Scout_mini_navigation/go2_webrtc）
- 接入点：
  - 自研 3D：`/home/jetson/kn_nav/src/pct_scan_navigation/scripts/go2_cmd_vel_bridge.py`
  - 外协 3D：`/home/jetson/docker_ws_backup/src/robot_web_controller/scripts/robot/unitree_go2/sdk/go2_sdk_manager.py`
- Go2 控制需把 `/cmd_vel` 转成 `client.Move(x,y,z)` 类指令（区别于 Scout mini 直接响应 /cmd_vel）。

## 2. 虚拟 MAC 地址（外协 3D 导航授权校验）
- 外协 3D 导航的 `global_planner` 节点内置 MAC 白名单校验，不匹配则 exit code 1 静默退出。
- 绑定的 2 个 MAC：雷达 `00:e0:9a:2f:15:e6`、usb转网口 `9c:69:d3:1e:3e:96`（未绑定狗 MAC）。
- 实际二进制检查的网卡接口名：`eth30/eth2/eth10/eth0/ens33/wlan0/en0`（源码片段里的 enp2s0 实际不存在）。
- 授权 MAC `9c:69:d3:1e:3e:96` 需挂在上述某接口名下才能过校验。
- 虚拟方法：`nmcli connection modify eth0-static ethernet.cloned-mac-address 00:e0:9a:2f:15:e6`（同理 eth2）。
- 故障现象：`REQUIRED process [global_planner-7] has died! exit code 1`，无业务日志。
- 诊断：`ip -br link | grep 9c:69:d3:1e:3e:96` 看 MAC 挂哪个接口名。

## 3. ROS1 ↔ ROS2 通信
- 用 `ros:foxy-ros1-bridge` 镜像（Noetic + Foxy）跑 dynamic_bridge。
- 场景：宿主机 ROS1（雷达驱动）→ 桥接 → 自研 3D 导航容器 ROS2。
- 命令要点：宿主机执行，`ROS_MASTER_URI=http://127.0.0.1:11311`，`ROS_DOMAIN_ID=0`，`--bridge-all-topics`。
- 注意：该命令不启动 roscore，需先有 roscore + 雷达驱动。

## 4. 导航时间戳（雷达 vs 系统时间不一致）
- 问题：雷达时间每次开机从固定值开始，与系统时间（现在）不一致。
- 解决：`use_sim_time=true`，让导航读 `/clock`；`/clock` 由 `/livox/imu` 发布时一并发布。
- 代码改动：`livox_ros_driver2/src/lddc.cpp` PublishImuData 新增 clock 发布、`lddc.h` 加 clock_pub_、`ros1_headers.h` 引入类型；外协 dev_start.sh 设 /use_sim_time。
- 遗留：`/livox/lidar` 和 `/livox/imu` 两个线程，雷达可能先发布导致时间戳跑到 /clock 前面，报 "Lookup would require extrapolation" 警告，暂不影响导航。
- 注意：外协 dev_start.sh 里 /use_sim_time 设置在 source ROS/roscore 之前，失败也可能打印成功；建议移动到 roscore 启动后。

## 5. Claude Code 在 D360 中的使用
- 网络：ssh 反向代理流量到本机（前提：笔记本/台式机已配好可用代理）。
- .bashrc：`export http_proxy=http://127.0.0.1:7890`、`https_proxy` 同上；测试 `curl -x http://127.0.0.1:7890 https://www.google.com`。
- 三个导航项目的 Claude Code 对话记忆目录：/home/jetson/Scout_mini_navigation、/home/jetson/kn_nav、/home/jetson/docker_ws_backup（可 `claude -r` 查看历史）。

## 6. 网络/硬件地址约定
- Go2：192.168.123.161（STA/WebRTC）
- Livox MID-360：192.168.123.120（主机接收 192.168.123.164）
- 2D 前端：http://192.168.31.132/app/
- 外协 3D Web：http://192.168.31.132:9000（admin/admin）
- 绿联云：/volume1/实习生/D360/{2D导航, 自研3D导航, 外协3D导航, WebRTC}
