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

## 2. 离线语音识别：vosk —— **已于 2026-09-18 删除（废弃 demo）**

- 原位置：`/home/jetson/vosk`（**只在 701 上**，715 从来没有）；模型 `vosk-model-small-cn-0.22`
- 原功能：实时流式转写（打字机效果）、拼音纠错（同音字"见图"→"建图"）、识别结果 HTTP POST
- `myvosk.py`：主程序；`TARGET_PHRASES` 13 条（开始建图/建图完毕/结束建图/保存地图/标记目标点/导航到/带我去/到我跟前/打招呼/蹲下/趴下/转圈/站起来），拼音滑窗相似度阈值 0.75

**为什么删**（2026-09-18 用户确认）：
1. **从未被任何东西启动** —— crontab 无、systemd 无、无进程、无脚本调用（删前逐项核查）
2. git 状态是实验品：`origin` **未配 remote**、**只有 1 个提交**（`fa33312 直接预设词`）、工作树有未提交改动
3. **功能与生产链路重叠**：那 13 个命令词现在由 `run_mic.py` + nav `/api/voice/intent` 处理
4. **它不能解决"无网现场"** —— 它只做 ASR，而 ASR 本来就离线（本地 sherpa-onnx 模型）；真正缺的是**离线 TTS**（见下）

**删除执行**：`rm -rf /home/jetson/vosk`（释放 191M）。因源码不可恢复（无 remote + 有未提交改动），删前留了**源码备份**
`/home/jetson/vosk-source-backup-20260918.tar.gz`（**23K**，含 `myvosk.py`/README/.git，不含 venv 与模型）—— 确认无用后可一并删。

> ⚠️ 若日后要**无网可用的语音能力**，方向不是 vosk，而是**离线 TTS**（`sherpa-onnx` 自带 TTS 模型，与现用识别引擎同源、可复用同一套依赖），外加 nav 侧 `tts_cache` 预热。详见 `tasks/voice-containerization-plan-2026-09-18.md`。

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
## 7. R1 麦克风阵列与 D360/BOX 设备关系（用户确认，2026-08-20）
- 硬件拓扑：R1 麦克风阵列搭载在 BOX 设备上；BOX 通过一根网线和一根 USB 线连接到 D360。
- D360 设备组成：Jetson 主板、雷达、RTK、相机、网卡及电源模块等。
- 当前状态：用户已更换 BOX；新 BOX 已完成物理连接并通电，待在 Jetson 上进行设备枚举和录音/语音交互测试。
- R1 资料来源：用户提供《R1麦克风阵列模块大模型语音交互功能部署》文档及其中的 Yahboom R1 资料链接。
- 文档确认的 USB 设备：
  - 六麦 UAC：`ListenGo Circular 6-Microphone`，VID:PID `2208:0001`。
  - 串口通信：`QinHeng USB`，VID:PID `1a86:7523`。
- 文档建议的 udev 规则：
  - `2208:0001` 绑定 `/dev/lg_speech_uac`。
  - `1a86:7523` 绑定 `/dev/lg_speech_serial`。
  - 如遇重复设备 ID，需结合实际 `ATTRS{devpath}` 区分，禁止直接猜测 devpath。
- 语音程序：`/home/jetson/xf_chat_standalone`；启动示例 `PORT=/dev/lg_speech_serial ./run.sh`。
- 预期验收：`lsusb` 出现两个设备、`ls /dev/lg*` 出现绑定设备；启动后唤醒词“ 小飞小飞 ”应得到“我在”，并完成录音、ASR、星火回复和 TTS 播放。
- 安全备注：文档中的讯飞 API 凭证、模型配置和在线服务开通步骤不写入工作台；如需配置必须使用用户自己的凭证，禁止记录明文密钥。
