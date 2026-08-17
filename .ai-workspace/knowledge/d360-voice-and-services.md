# D360 语音与辅助服务（板内盘点 2026-08-17）

> 板内只读盘点所得。语音功能横跨多个独立项目/服务。

## 1. 六麦阵列语音对话：xf_chat_standalone（讯飞）
- 位置：`/home/jetson/xf_chat_standalone`（自包含，**无需 ROS2**）
- 链路：唤醒 → 录音 → **讯飞在线 ASR** → **星火大模型**流式回复 → **讯飞 TTS** 播报
- 关键文件：
  - `xf_mic_chat_standalone.py`：主程序
  - `serial_reader.py`：串口协议（唤醒事件/原始音频），等价原 C++ `mic_serial_node`；设备 `/dev/lg_speech_serial`（六麦阵列 \`ListenGo\`，ALSA keyword）
  - `spark_api.py`：讯飞在线 ASR/TTS/星火（WebSocket）
  - `robot_cmd_publisher.py`：控狗 —— 发布 **ROS1 `/voice_command`（std_msgs/String）**
  - `intent_router.py`：控狗意图关键词路由
  - `xf_config.yaml`：凭证/模型/音频源/VAD
  - `run.sh`：一键启动（`PORT=/dev/lg_speech_serial`）
- 依赖：Python 3.7+、ROS1 rospy（控狗）、ALSA aplay、portaudio19-dev
- 备注：控狗经 ROS1 `/voice_command`，需 `roscore`

## 2. 离线语音识别：vosk
- 位置：`/home/jetson/vosk`（模型 `vosk-model-small-cn-0.22`）
- 功能：实时流式转写（打字机效果）、**拼音纠错**（同音字"见图"→"建图"）、识别结果 **HTTP 推送**
- `myvosk.py`：主程序；`TARGET_PHRASES` 含 "开始建图" 等命令
- 用途：建图/命令等场景的离线指令识别

## 3. 2D 导航喊话回传（Scout_mini_navigation/nav_api）
- `fastapi_service/voice.py`：**语音指令文本解析与派发**；APP 麦与环形麦识别成文本后统一调 **`POST /api/voice/intent`**；环形麦多带 `bearingDeg` 方位
- `fastapi_service/audio.py`：音频采集/播放（Opus/ALSA，麦克 `plughw:3,0`）
- 契约文档：`src/nav_api/docs/voice_audio_contract.md`
- 关联：SLAMIBotApp codex 分支有**蓝牙耳机双向喊话**（2 秒切换延迟）

## 4. RTSP 视频流 / 图传：rtsp_server（MediaMTX）
- 位置：`/home/jetson/rtsp_server`
- 组件：`mediamtx` v1.9.0（linux/arm64v8）+ `mediamtx.yml`
- 用途：相机 RTSP 流（图传），配合 SLAMIBOT_D360_Framework 的 oak_rtsp_pusher.py

## 5. 4G 远程连接：4g_connect.sh
- 位置：`/home/jetson/4g_connect.sh`
- 功能：Quectel 4G 模块（EG25 / EC800K；RNDIS/ECM）AT 配置 usbnet，`APN=cmnet`，接口 `usb1`
- 用途：板子 4G 上网（配合走 ssh 反向代理/公网访问）

## 6. 板内其它项目（未深挖，待后续）
- `SLAMIBOT_D360_Framework`：D360 整机驱动框架（livox 驱动 /clock 时间戳修复 + OAK 相机 RTSP）
- `rtk_record`、`b74_record`：RTK / 数据记录
- `unitree_sdk2_python`：宇树 SDK2 Python
- `cyclonedds`：CycloneDDS（ROS2 RMW）
- `livox_bridge_ws`：livox 桥接工作区
- `nav_frontend_redesign`：前端重设计（待确认）
- `Cartographer_ws` / `catkin_ws` / `caktin_ws`：旧/备用工作区
- 大量 rosbag（lidar_camera*.bag 等）在 `~`