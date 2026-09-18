# 六麦阵列语音对话（自包含独立版，无需 ROS2）

把**整个 `xf_chat_standalone` 文件夹**拷到 Linux 系统里，安装依赖后即可直接运行，实现"唤醒 → 录音 → 在线识别 → 星火大模型流式回复 → 在线语音播报"的对话功能，全程不依赖 ROS2。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `xf_mic_chat_standalone.py` | 主程序（去 ROS2 版自由对话） |
| `serial_reader.py` | 串口协议实现（唤醒事件 / 原始音频），等价原 C++ `mic_serial_node` |
| `spark_api.py` | 讯飞在线 ASR / TTS / 星火大模型（WebSocket） |
| `robot_cmd_publisher.py` | 控狗：ROS1 `/voice_command`（std_msgs/String）发布 |
| `intent_router.py` | 控狗意图关键词路由 |
| `xf_config.yaml` | 配置文件（凭证、模型、音频源、VAD 参数等） |
| `requirements.txt` | Python 依赖 |
| `run.sh` | 一键启动脚本 |

## 运行环境要求

- Linux（已连接六麦阵列硬件）
- Python 3.7+
- ROS1（控狗需 `rospy` / `std_msgs`，运行前 `source` 环境并启动 `roscore`）
- 系统命令 `aplay`（ALSA，用于播放）：`sudo apt install alsa-utils`
- 编译 PyAudio 可能需要：`sudo apt install portaudio19-dev python3-dev`

## 安装与运行

```bash
# 1. 进入文件夹
cd xf_chat_standalone

# 2. 安装依赖（建议用虚拟环境）
pip3 install -r requirements.txt

# 3. 赋予启动脚本执行权限
chmod +x run.sh

# 4. 运行（按实际串口设备修改 PORT）
PORT=/dev/lg_speech_serial ./run.sh
# 或直接调用：
python3 xf_mic_chat_standalone.py --port /dev/ttyUSB0
```

启动后说出唤醒词即可开始对话；模型播报过程中再次唤醒可打断。`Ctrl+C` 退出。

## 配置说明（`xf_config.yaml`）

凭证已填入（使用讯飞 **WebSocket** 那组）：

```yaml
appid: "你的APPID"          # APPID
api_key: "你的APIKey"   # APIKey
api_secret: "你的APISecret" # APISecret
spark_model: "pro"         # 对应 Spark Pro (v3.1)
audio_source: "alsa"       # alsa=PyAudio读USB声卡；raw=控制串口直传原始音频
```

> 注意：HTTP 接口那组 Bearer token 本程序用不到。
> 也可用环境变量覆盖：`SPARK_APP_ID` / `SPARK_API_KEY` / `SPARK_API_SECRET`。

## 音频源说明

- `audio_source: alsa`（默认）：用 PyAudio 从名称含 `ListenGo` 的 USB 声卡采集；唤醒仍走控制串口。
  - 设备名关键词可改：`--device-keyword 你的关键词`。
- `audio_source: raw`：唤醒和音频都走控制串口（硬件原始音频，取 channel0），无需 PyAudio。

## 常用参数

```bash
python3 xf_mic_chat_standalone.py \
  --port /dev/lg_speech_serial \   # 控制串口
  --baudrate 115200 \
  --audio-source alsa \            # alsa / raw（默认跟随配置文件）
  --device-keyword ListenGo \      # alsa 设备名关键词
  --spark-model pro \              # lite/pro/pro-128k/max/max-32k/ultra
  --tts-voice x4_yezi \
  --silence-timeout 1.5 \
  --max-record-time 30 \
  --audio-dir ./audio              # 唤醒提示音 wakeup.wav 所在目录（可选）
```

## 唤醒提示音（可选）

程序唤醒时会播放 `wakeup.wav`。若没有该文件，会自动改用在线 TTS 播报"我在"。
如需用本地提示音，把 `wakeup.wav` 放到 `xf_chat_standalone/audio/wakeup.wav` 即可。

## 语音控狗（ROS1）

ASR 后规则意图优先于闲聊。命中控狗意图时，向 ROS1 话题 **`/voice_command`** 发布 `std_msgs/String`（可用 `ros_cmd.topic` 修改）。

**运行前**需已 `source` ROS1 环境，并确保 `roscore`（或 master）在跑。下游节点自行订阅并解释字符串。

| 说法 | 话题 `data` |
|------|-------------|
| 过来 / 到我这儿… | `come_here` |
| 去XX / 到XX / 导航到XX | `goto:<ASR原文>`（例：`goto:去客厅`） |
| 取消导航 / 不去了… | `nav_cancel` |
| 暂停导航… | `nav_pause` |
| 继续导航… | `nav_resume` |
| 站起来 / 站立 / 起身 | `stand_up` |
| 趴下 / 蹲下 / 卧倒 | `lie_down` |
| 招手 / 打招呼 / 挥挥手 | `wave` |
| 其它 | 星火闲聊（不发话题） |

监听示例：

```bash
rostopic echo /voice_command
```
该目录demo运行

```bash
# 在终端1里边运行如下命令，这部分接收/voice_command，并根据数据控制狗
export UNITREE_ROBOT_IP=192.168.123.161
python3 dog_run_with_vioce.py

# 在终端2里边运行如下命令，这部分用于接收语音，然后处理语音发布rostopic
PORT=/dev/lg_speech_serial ./run.sh
```

配置见 `xf_config.yaml` 的 `ros_cmd` / `intent`。

单元测试：`python3 -m pytest tests/ -v`

**互斥：** 勿与旧 `voice_main` 麦克风线程同时运行。

## 提示

`xf_config.yaml` 含真实密钥，请勿上传到公开仓库。
