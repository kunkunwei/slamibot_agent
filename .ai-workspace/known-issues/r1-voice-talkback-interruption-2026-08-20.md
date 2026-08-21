# R1 语音识别与 APP 喊话/回传链路冲突

- 日期：2026-08-20
- 现象修正：APP 喊话本身不会直接打断语音识别；但 APP 音频经 BOX 扬声器播放后产生啸叫/声学回授，导致唤醒后语音采集几乎没有有效能量，进而难以完成识别。
- BOX 判断：当前 BOX 不是项目阻塞项，已有其它 BOX 可替换。
- 新日志：R1 UAC 已识别为 `ListenGo Circular 6-Microphone: USB Audio (hw:3,0)`，音频流可打开；唤醒词可识别，但唤醒后录音峰值仅 `0` 或 `17`，VAD 阈值为 `500`。

## 启动日志证据

执行：

```bash
PORT=/dev/lg_speech_serial ./run.sh
```

结果：

- `/dev/lg_speech_serial` 可以打开；
- 波特率 `115200`；
- 串口驱动启动成功；
- 握手确认消息发送成功；
- ALSA 找不到包含 `ListenGo` 的音频设备；
- 可见设备包括 `USB Audio Device (hw:2,0)`、Jetson APE 多个输入设备、`pulse` 和 `default`；
- 最终报错：`ALSA 音频采集启动失败，退出`。

## 当前判断

- 串口控制链路与音频采集链路至少部分分离：串口可用，但 `ListenGo` UAC 音频设备未被音频适配器发现。
- APP 喊话/回传可能改变 USB 音频设备占用、ALSA 路由、Pulse 音频默认设备或 BOX 声卡工作模式；这只是待验证假设，不是已确认根因。
- 当前不能仅凭 `USB Audio Device (hw:2,0)` 认定它就是 R1 麦克风，需要结合 `lsusb`、`arecord -l/-L`、udev 规则、设备插拔前后差异和 APP 喊话状态确认。

## 下一步建议

1. 分别在 APP 喊话链路空闲、开启、结束后采集 `lsusb`、`arecord -l`、`arecord -L` 和 `/dev/snd` 状态。
2. 检查 `xf_mic_chat_standalone` 的 ALSA 设备匹配逻辑，确认是否硬编码搜索 `ListenGo` 名称。
3. 确认 APP 喊话是否占用同一个 USB 声卡或切换 Pulse 默认设备。
4. 在不改生产配置前，使用明确设备名/硬件卡号做独立录音探针。
5. R1 设备更换后优先复测同一套对比状态。

