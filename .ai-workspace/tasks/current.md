# 当前任务（current）

> 只记录尚未完全验收或仍需人工决策的任务。已完成操作及证据见 `completed.md`。

## TASK-2026-08-21-001：图传接收机 IP、BOX 麦克风、任务 service 模式与 GO2 适配

- goal: 完成 2026-08-21 用户布置的多项待办并形成后续执行入口（仅记录，不擅自实现）
- project: navigation-ros1-d360 + frontend-app + deployment
- technology: ros1（CURRENT）；GO2 适配待定
- lifecycle: CURRENT
- migration: NEEDS_CONFIRMATION（GO2 适配若涉及 ROS2/DDS/迁移，未经授权不得触发；当前仅记录为待确认项）
- status: in_progress
- scope: NEEDS_CONFIRMATION（多子项目标地址、设备路径、接口契约、底盘型号均需用户确认）
- authorized_paths:
  - `F:\slamibot_agent\.ai-workspace\tasks\current.md`（本任务条目）
  - `F:\slamibot_agent\.ai-workspace\tasks\context-checkpoint.md`（同步检查点）
- forbidden:
  - 未经授权不得修改 ROS Topic/Service/Action、消息格式、参数、launch、地图、数据库 schema。
  - 未经授权不得改动 Jetson 系统、Docker 基础设施、ROS 工作区结构、rosbridge 接口、APP/WEB 前后端契约。
  - 未经授权不得更换或重写底盘驱动（Scout → GO2 涉及迁移/适配，需独立专项授权）。
  - 未经授权不得进行 ROS1 → ROS2 迁移；GO2 适配的最终技术栈以用户确认为准。
  - 不得擅自补充未知 IP、设备名、接口路径或实现方案；缺失值一律标 UNKNOWN / NEEDS_CONFIRMATION。
- todo:
  - 1. 修改 IP 地址为图传接收机：
      - 当前/原 IP：UNKNOWN
      - 目标 IP（地址）：UNKNOWN / NEEDS_CONFIRMATION（需用户给出图传接收机的目标地址与所属网段）
      - 目标主机/设备名：UNKNOWN
      - 网关/掩码：UNKNOWN
      - 备注：当前任务条仅登记需求，不执行任何网络/系统修改。
  - 2. 插拔 BOX USB，确认麦克风是否在线：
      - 现状参考：`TASK-2026-08-20-008`（`/dev/lg_speech_serial` 可握手，ALSA 未见 `ListenGo`）。
      - 待做：插拔 BOX USB 后重新检查 `lsusb`、udev、`/dev/lg_speech_uac`、ALSA 设备；不得擅自写入 udev 规则。
      - 验收：ALSA 中再次出现 `ListenGo` 音频设备且语音识别可启动。
      - 2026-08-21 lsusb 证据（用户提供，仅记录，不在本任务中执行命令）：
          - 插拔前：`lsusb` 列出 2 个 `1a86:7523 QinHeng Electronics HL-340 USB-Serial adapter`；未出现 `2208:0001 ListenGo Circular 6-Microphone`；也未识别出明确的 USB Audio 麦克风设备。
          - 插拔后：`lsusb` 列出 3 个 `1a86:7523 QinHeng Electronics HL-340 USB-Serial adapter`，并新增 `0d8c:0012 C-Media Electronics, Inc. 4-Port USB 2.0 Hub`、`2c7c:0125 Quectel EC25 LTE modem` 以及额外的 Hub；仍未出现 `2208:0001 ListenGo Circular 6-Microphone`。
          - 结论：仅凭 `lsusb` 不能确认麦克风在线；当前证据更支持 BOX 插拔触发了 USB 拓扑/串口设备重枚举，但**未枚举出预期 ListenGo 麦克风**。不得把 `C-Media Electronics` Hub 直接判定为麦克风。
      - 2026-08-21 后续 Jetson 检查证据（用户提供，仅记录，不在本任务中执行命令）：
          - `lsusb -t`：Bus 01 Port 2 Dev 11 同时存在 HID 与 Audio 接口；Audio 接口由 `snd-usb-audio` 驱动。说明 USB 音频设备已被内核枚举并加载驱动。
          - `arecord -l`：列出 `card 2: Device [USB Audio Device], device 0: USB Audio [USB Audio]`。这是目前最强的「麦克风/USB 音频采集设备在线」证据，但设备名称是通用 `USB Audio Device`，**不能直接确认为 ListenGo**。
          - `arecord -L`：列出 `sysdefault:CARD=Device`、`hw:CARD=Device,DEV=0`、`plughw:CARD=Device,DEV=0` 等 USB Audio PCM。注意它同时列出播放/输出 profile，**不能仅据此证明录音质量或语音识别可用**。
          - 设备节点：`/dev/lg_speech_uac` 不存在；`/dev/lg_speech_serial -> ttyUSB8` 存在。
          - 失败项：`dmesg -T | tail -n 100` 因权限失败（不允许访问内核缓冲区）；`udevadm info ...` 因使用占位参数 `...` 而失败——这两项**不应**作为设备不存在的证据。
          - 结论修订：USB 音频设备在线，麦克风链路已达到「系统识别」阶段；但 ListenGo 身份、录音数据、语音识别链路、`/dev/lg_speech_uac` 是否被 udev 创建仍未完成确认。
          - 麦克风结论：`NEEDS_CONFIRMATION`，任务状态保持 `in_progress`，**不得标记为完全验收**。
      - 2026-08-21 BOX 扬声器与采集链路事实补充（用户提供，仅记录，不在本任务中执行命令）：
          - BOX 集成扬声器与麦克风；**扬声器/播放链路此前已由用户人工实测确认正常**（这是已确认事实）。
          - 本次 `arecord`/`snd-usb-audio` 证据**仅针对 USB 音频设备及采集接口在线**；**不能用「扬声器正常」反推「麦克风采集正常」**——播放与采集是两条独立物理/逻辑通道，ALSA 设备节点、profile 与驱动行为不同，扬声器正常不构成麦克风录音/语音识别可用的证据。
          - 当前准确状态（区分播放与采集）：
              - BOX 音频输出（扬声器播放）：已由用户人工实测确认。
              - USB 音频输入设备：已被系统识别并由 `snd-usb-audio` 驱动枚举（`arecord -l`/`arecord -L` 列出 `USB Audio Device`）。
              - 麦克风实际录音与语音识别：仍 `NEEDS_CONFIRMATION`（设备名仍是通用 `USB Audio Device`，非 `ListenGo Circular 6-Microphone`）。
              - `/dev/lg_speech_uac`：仍不存在。
      - 2026-08-21 用户在 Jetson 执行的 5 秒短时录音证据（用户提供，仅记录，不在本任务中执行命令）：
          - 命令：`arecord -D plughw:CARD=Device,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 /tmp/box-mic-test.wav`。
          - 终端输出：显示“正在录音 WAVE '/tmp/box-mic-test.wav' : Signed 16 bit Little Endian, 16000Hz, Mono”，随后回到 shell，无报错。
          - 结论：ALSA 已成功打开该 USB 采集设备并完成 5 秒录音流程；这是“录音设备可打开/采集流程完成”的证据。
          - 边界（**不得过度宣称**）：
              - 终端未给出 wav 文件大小；未运行 `file`/`aplay` 回放；未提供波形或语音识别结果。
              - 因此**不能据此宣称“已经听到声音”或“语音识别正常”**。
              - 麦克风硬件/ALSA 采集基本可用；实际音频内容与语音识别仍 `NEEDS_CONFIRMATION`。
          - 2026-08-21 用户在 Jetson 完成的 WAV 文件静态校验证据（用户提供，仅记录，不在本任务中执行命令）：
              - `ls -lh /tmp/box-mic-test.wav`：文件大小 `157K`（157 KB，1 KB = 1024 B）。
              - `file /tmp/box-mic-test.wav`：`RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 16000 Hz`。
              - 结论升级：录音文件已成功生成，大小约 157K，与 5 秒、16kHz、16-bit、mono 的预期（约 160 KB，扣除 WAV 头 44 B）一致；文件格式有效。由此确认 **USB 麦克风采集链路在 ALSA 层工作正常**。
              - 边界（**不得过度宣称**）：用户尚未提供 `aplay` 人工回放结果或语音识别结果，**不得宣称"已听到具体声音"或"语音识别正常"**。
              - 当前状态：
                  - BOX 扬声器（播放链路）：已确认正常。
                  - 麦克风录音采集（`arecord` + WAV 落盘 + 格式校验）：**已确认正常**。
                  - 实际音频内容/清晰度、语音识别链路：仍 `NEEDS_CONFIRMATION`。
                  - `/dev/lg_speech_uac`：仍不存在。
              - 下一步建议（**仅记录，不在本会话执行**）：`aplay /tmp/box-mic-test.wav` 人工确认声音，随后进行最小语音识别测试；不执行。
      - 2026-08-21 语音交互应用启动与人工回放证据（用户提供，仅记录，不在本任务中执行命令）：
          - 启动命令：`PORT=/dev/lg_speech_serial ./run.sh`。
          - 串口链路：成功打开 `/dev/lg_speech_serial`，115200 baud；`mic_serial` 启动成功，`raw_audio=false`。
          - 设备枚举：包含 `USB Audio Device: - (hw:2,0) (输入通道: 1)`，以及 Jetson APE 设备、`pulse`、`default` 等。
          - 错误：未找到包含 `ListenGo` 的音频设备；最终 `ALSA 音频采集启动失败，退出`。
          - 录制输出：应用将"录音"写入 `/dev/null`——**不要把它当作有效录音文件**（`/dev/null` 是空设备，写入即丢弃）。
          - 人工回放：用户执行 `aplay /tmp/box-mic-test.wav`，命令正常完成、未报错，但**用户没有听到录音**。
          - **更新结论**：
              - 串口链路：正常（`mic_serial` 启动成功）。
              - USB 音频采集设备：存在并可打开（`hw:2,0`）。
              - 应用按名称匹配 `ListenGo`，未识别通用 `USB Audio Device`，**语音交互应用启动失败**。
              - **不得把"应用启动失败"等同于"麦克风硬件坏"**；USB Audio Device 已被 `snd-usb-audio` 驱动枚举。
          - **三个问题必须区分**：
              ① 应用设备名匹配失败（ListenGo vs 通用 USB Audio Device）。
              ② 录音文件可能全静音/增益为零（与播放链路无关）。
              ③ 扬声器播放链路此前已确认正常，但本次 WAV 回放未听到声音，可能是播放设备/音量/路由问题，**暂不猜根因**。
          - 当前准确状态：
              - 串口（`mic_serial`）：已确认启动成功。
              - USB 音频采集设备（`hw:2,0`）：已被系统识别，可被 ALSA 打开。
              - 语音交互应用：因名称匹配 `ListenGo` 失败而退出，**未真正进入采集**。
              - 应用写入 `/dev/null` 的"录音"：**不是有效录音**。
              - `/tmp/box-mic-test.wav`：来自此前 `arecord` 测试，文件格式/落盘已确认正常；本次 `aplay` 命令正常但用户未听到声音。
              - 麦克风实际有效音频、语音识别、WAV 实际播放结果：仍 `NEEDS_CONFIRMATION`。
              - 扬声器链路：此前已确认正常，本次回放结果需进一步确认（不直接否定扬声器）。
          - 下一步建议（**仅记录，不在本会话执行**；待用户授权后再跑）：
              - 在应用配置/代码中查找 `ListenGo` 名称匹配规则；决定改成按设备名前缀/正则匹配或加设备别名映射。
              - 用 `amixer`/`alsamixer` 检查 USB Audio capture mixer、Capture 开关和增益。
              - 用 `arecord -D plughw:CARD=Device,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 -V mono /tmp/box-mic-test.wav` 观察实时 VU/峰值表。
              - 之后用 `sox /tmp/box-mic-test.wav -n stat` 或 `ffmpeg -i /tmp/box-mic-test.wav -af volumedetect -f null -` 检查录音是否全零。
              - 用 `aplay -L` 看默认播放 PCM；用 `aplay -D plughw:CARD=Device,DEV=0 /tmp/box-mic-test.wav` 强制走 USB Audio 输出确认播放路由。
              - 必要时 `lsusb -v -d 0d8c:0012`（只读）确认 C-Media 设备身份。
              - **不得修改 udev 规则或应用代码**，除非后续明确授权。
          - 任务执行约束：上述命令本次**不执行**，仅记录到任务条目；后续是否在 Jetson 上执行需用户授权。
      - 下一步建议（**仅记录，不在本会话执行**；待用户授权后再跑）：
          - 短时录音测试，例如 `arecord -D plughw:CARD=Device,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 /tmp/box-mic-test.wav`，随后 `aplay` 校验文件或最小语音识别测试。
          - 用正确绝对路径执行 `udevadm info --query=all --name=/dev/ttyUSB8`，并对实际声卡节点跑 udev 查询（实际节点需先从 `/proc/asound/cards`、`/dev/snd` 确认，未知处标 UNKNOWN）。
          - 重试 `dmesg`（需具有 sudo 或内核日志权限时再执行）。
      - 任务执行约束：上述命令本次**不执行**，仅记录到任务条目；后续是否在 Jetson 上执行需用户授权（涉及只读命令，可纳入 READ_ONLY 范围后由用户触发）。
  - 2026-08-21 用户最新音频诊断证据（用户提供，仅记录，不在本任务中执行命令）：
      - `arecord ... -V mono`：可完成 5 秒录音，但 VU 输出几乎没有有效电平（仅看到起始 `#+ ... | 00%`，不可据此做精确峰值判断）。
      - `sox`：未安装（两次均 `sox：未找到命令`）。
      - `ffmpeg -i /tmp/box-mic-test.wav -af volumedetect -f null -`：
          - n_samples = 80000（约 5 秒，16kHz mono，与预期一致）。
          - mean_volume = -90.3 dB。
          - max_volume = -74.7 dB。
          - histogram_74db / histogram_76db 仅有少量样本。
          - 明确说明 WAV 内容基本接近静音/只有极低噪声。
      - `amixer`：输出非常长，主要是 Jetson APE / 内部 DSP / I2S / DSPK 控件；用户未指定 `-c 2`，因此不能把它当作 USB Audio Device (card 2) 的采集增益/静音状态证据。
      - **结论升级**：
          - USB 音频设备枚举、ALSA 打开、WAV 格式/落盘都正常。
          - 但录音内容基本为静音（mean ≈ -90 dB, max ≈ -75 dB），说明当前有效麦克风音频未进入 `hw:2,0`（或输入增益/静音/路由/设备身份仍有问题）。
          - **不得宣称麦克风硬件已损坏**；可能原因标为 `NEEDS_CONFIRMATION`：
              - USB 音频设备并非 BOX 麦克风输入（device 身份/路由问题）。
              - 采集通道静音或增益为 0。
              - USB Audio 设备身份/驱动映射错误。
              - 需要特定多通道/采样格式才能采集到有效数据。
      - **至少有两层问题**（不要简化为单一名称匹配）：
          - ① 应用设备名识别失败（ListenGo vs 通用 USB Audio Device）。
          - ② 采集数据近静音（与播放/识别链路无关）。
      - 当前准确状态（再次区分播放与采集）：
          - BOX 音频输出（扬声器播放）：此前已由用户人工实测确认正常。
          - USB 音频输入设备：已被系统识别并由 `snd-usb-audio` 驱动枚举（`arecord -l`/`arecord -L` 列出 `USB Audio Device`）。
          - ALSA 打开 + WAV 落盘：已确认正常（文件格式校验通过）。
          - 麦克风有效音频内容 / 语音识别：`NEEDS_CONFIRMATION`（WAV 接近静音）。
          - 语音交互应用：仍因名称匹配 `ListenGo` 失败未启动。
          - `/dev/lg_speech_uac`：仍不存在。
      - 下一步建议（**仅记录，不在本会话执行**；待用户授权后再跑）：
          - 用 `amixer -c 2 scontrols`、`amixer -c 2 contents` 检查 USB 声卡真实控件（不能继续只看默认 APE）。
          - 查看 `cat /proc/asound/cards`、`cat /proc/asound/card2/usbid`（若存在）、`ls -l /dev/snd`。
          - 用 `ffmpeg` 已可用，继续用它判断不同通道/格式；可试 `arecord -D hw:CARD=Device,DEV=0 -f S16_LE -r 16000 -c 1 -d 5 ...` 与 `-c 2`（先 `arecord --dump-hw-params`，仅记录建议）。
          - 对 USB 声卡执行 `lsusb -v -d 0d8c:0012`（只读）确认描述符/厂商。
          - 检查应用源码/配置的 `ListenGo` 匹配逻辑，暂不修改。
      - 任务执行约束：上述命令本次**不执行**，仅记录到任务条目；后续是否在 Jetson 上执行需用户授权。
  - 3. 确认任务创建相关内容采用 service 模式：
      - 当前事实源：`/api/map/task/*`、`/api/map/nav_multi/*` 为 HTTP 接口；ROS 内部使用 `move_base` action 与 `/nav_multi/*` service/status（见 `TASK-2026-08-20-010`）。
      - 待确认：用户所指“任务创建”具体指 HTTP 入口、ROS service 还是二者并行；接口契约以用户确认为准。
  - 4. 实现/验证语音识别到点位导航、任务创建：
      - 依赖：TASK-2026-08-21-001 #2（麦克风在线）与 #3（service 模式确认）。
      - 范围：仅在确认后再展开；当前不实现任何业务代码。
  - 5. 点位动作测试和接口开发，通用 service 示例：
      - 通用 service 示例（暂留，待实现验证）：
        - `take_photos(n=10)`：拍照 10 张。
        - `drive_forward(distance_m=2)`：前进 2 米。
        - `announce(text="我到了")`：喊话"我到了"。
      - 执行语义：动作执行时暂时打断导航，完成后继续导航。
      - 待确认：动作实现的接入点（HTTP service / ROS service / nav_multi 内部回调）、打断/恢复机制、是否需要鉴权与幂等。
  - 6. 适配 GO2 的 2D 导航，测试更换底盘后能否正常工作：
      - 底盘型号：GO2（厂商/型号/驱动来源：UNKNOWN / NEEDS_CONFIRMATION）。
      - 与现有基线关系：当前 ROS1 + Scout 为 CURRENT（见 `facts/robot_profile.yaml` 与 `TASK-2026-08-20-010`）；GO2 适配若涉及驱动替换、TF、launch、参数或栈迁移，必须 `migration: true` 独立专项授权。
      - 当前结论：仅记录需求，不进行任何底盘相关修改。
- validation:
  - 当前不运行任何测试、构建、仿真、Jetson 操作。
  - 子项推进时再按 `testing-rules.md` 选取与风险相称的验证。
- rollback:
  - 本任务仅做登记，未触碰任何业务仓库；若误改，按 `git-safety.md` 用 `git checkout -- <file>` 回退或删除目录。
- tests: SKIPPED (task recording only)；本次新增的语音交互应用启动与人工回放证据同样仅记录，未在本任务中执行任何远程命令。

## TASK-2026-08-19-001：D360 前后端双 rosbridge 联调

- goal: APP/WEB 统一使用 9090，FastAPI/nav_api 内部保持使用 19090。
- project: frontend-app + navigation-ros1-d360 + deployment
- technology: ros1 + android + web + docker
- lifecycle: CURRENT
- migration: false
- status: in_progress
- authorized_scope:
  - `F:\SLAMIBotApp` 分支 `codex/native-compose-filament` 的默认 rosbridge 端口
  - Jetson `/home/jetson/Scout_mini_navigation/docker-entrypoint.sh`
  - Jetson `/home/jetson/Scout_mini_navigation/frontend/deploy/nginx.conf`
  - 指定 `scout-nav` 镜像/容器的构建、部署与验证
- forbidden:
  - 不修改摇杆代码或测试
  - 不修改 ROS Topic/Service/消息格式、导航算法、地图恢复内容或数据库结构
  - 不进行 ROS1→ROS2 迁移
- achieved:
  - Jetson 当前运行 `scout-nav:map2d-topic-copy-20260820`。
  - 9090 与 19090 同时监听，节点分别为 `/rosbridge_websocket`、`/scout_nav_rosbridge`。
  - Nginx `/rosbridge` 最终配置指向 `127.0.0.1:9090`。
  - FastAPI `/health` 返回 `rosbridgeConnected:true`。
  - APP `RobotEndpoint.DEFAULT_ROSBRIDGE_PORT` 已从 19090 改为 9090，已在提交 `3426f0a` 中提交并存在于远端 `codex/native-compose-filament` 分支。
- validation_history:
  - `RobotEndpointTest`: PASS
  - `assembleDebug`: PASS
  - 全量单测: 63/64；唯一失败是既有 G20 摇杆旧期望，与端口改动无关，未修改摇杆代码。
  - 2026-08-19 15:41 Jetson 只读复核: 80/5000/9090/19090 均监听，两个 rosbridge 节点均存在，`/health` 正常。
  - 2026-08-20 用户确认 WEB 与 APP 点位管理均已显示 2D 栅格地图；9090 `/map` CBOR 探针 PASS。
- remaining:
  - 地图与默认点云已通过 WEB/APP 人工验收；位姿和控制的完整端到端联调仍待执行。
  - 已在热点 `192.168.117.6` 与公司 Wi-Fi `192.168.31.135` 下完成 APP 实测。
  - 用户反馈：热点模式下进行导航时容易出现卡顿，但等待一段时间后可自行恢复；暂未形成稳定复现和根因结论。
  - 当前网络已从热点切换为公司 Wi-Fi，目标地址为 `192.168.31.135`。
- rollback:
  - APP：只回退 `RobotEndpoint.kt` 的单行端口修改。
  - Jetson：历史 scout-nav 容器/镜像已按用户授权删除；如需回退，基于远端分支 `codex/fix-initial-map-cloud` 的提交重新构建，不得依赖已删除容器。

## TASK-2026-08-19-004：地图清理遗留项人工决策

- goal: 决定 `test_map` 的关联数据如何处理，并复核 `office_room_test` 数据库记录是否应恢复。
- project: navigation-ros1-d360
- technology: ros1 + sqlite
- lifecycle: CURRENT
- status: needs_confirmation
- current_scope: READ_ONLY
- facts:
  - `test_map` 没有可用 2D 文件，数据库仍有 8 个点位、5 个任务、12 个任务点，未删除。
  - 已完成：删除 `test_map` 记录，并级联删除 8 个点位、5 个任务、12 个任务点。
  - 原备份已按用户要求删除；当前不保留本次 `test_map` 删除专用备份。
  - 验证：删除前后 `PRAGMA integrity_check` 均为 `ok`；删除后目标地图、点位、任务、任务点计数均为 0。
  - `office_room_test` 的数据库记录已删除，但同名 YAML+PGM 文件仍存在；可从清理前备份恢复该记录。
- forbidden:
  - 未经明确授权不得级联删除点位、任务、任务点。
  - 不得删除或覆盖地图恢复文件。
- validation:
  - 决策后再次执行 SQLite `PRAGMA integrity_check`，并核对 WEB `/app/points` 列表。
- rollback: 使用 `nav_api.db.pre-map-cleanup-20260819_141713.bak`，禁止直接覆盖当前库；应先停写并做新的当前库备份。







'

## TASK-2026-08-20-008：更换 BOX 后重新连接和测试 R1 麦克风

- status: in_progress
- scope: R1 麦克风设备识别、udev 绑定核对、音频输入和语音交互最小测试
- topology: R1 麦克风阵列搭载于 BOX；BOX 通过网线和 USB 连接 D360；D360 含 Jetson、雷达、RTK、相机、网卡和电源模块
- current_state: 当前 BOX 暂不作为项目阻塞项，已有其它 BOX 可替换；本次日志显示串口 `/dev/lg_speech_serial` 可打开并完成握手，但 ALSA 未找到 `ListenGo` 音频设备，语音识别启动失败。
- expected_devices: `ListenGo Circular 6-Microphone` (`2208:0001`)；`QinHeng USB` (`1a86:7523`)
- expected_paths: `/dev/lg_speech_uac`、`/dev/lg_speech_serial`
- source: 用户提供《R1麦克风阵列模块大模型语音交互功能部署》资料
- safety: 先只读检查 `lsusb`、udev 规则、设备节点、ALSA 和网络状态；不猜测重复设备的 `devpath`，不写入 API 凭证
- new_issue: APP 到 BOX 的喊话和回传链路可能打断语音识别；当前仅有现象和启动日志，根因待定位
'



## TASK-2026-08-20-009：2D 静态地图临时障碍“空气墙”

- project: navigation-ros1-d360
- technology: ros1 + move_base + costmap_2d
- lifecycle: CURRENT
- migration: false
- status: diagnosed
- current_scope: READ_ONLY
- symptom: 建图期间存在的临时障碍被写入二维静态地图；实物移走后，全局规划仍将该区域视为占据栅格。
- root_cause: 地图保存流程将 FAST_LIO 累积 PCD 投影为 PGM；导航的 `global_costmap/static_map: true` 加载该 PGM。`/scan` 虽启用 `marking` 与 `clearing`，但清除只作用于实时障碍层，不能擦除静态地图占据单元。
- preferred_solution: 静态地图只保留墙体、固定设施等结构；桌椅、纸箱、车辆等可移动物体交给实时 obstacle layer 标记和射线清除。
- immediate_options: 清场重建地图，或对确认区域离线修补 PGM/源 PCD 后生成新地图版本并人工验收。
- advanced_option: 若必须自动消除静态残影，新增保守的可变覆盖层，基于多帧、多视角自由空间证据及可编辑区域白名单覆盖静态占据；不得直接无条件清除静态层。
- validation: 对比 `/map`、`/move_base/global_costmap/costmap`、`/move_base/local_costmap/costmap` 与 `/scan`，确认残影首先存在于 `/map`。
- forbidden: 未授权不修改地图文件、costmap 参数、ROS 接口或 Jetson 运行环境。

## TASK-2026-08-20-010：导航点位与任务接口产品化审计

- project: navigation-ros1-d360 + frontend-app + deployment
- technology: ros1 + FastAPI + SQLite + Docker
- lifecycle: CURRENT
- migration: false
- status: assessed
- current_scope: READ_ONLY
- available_interfaces:
  - 点位 CRUD、排序、按当前 AMCL 位姿踩点：`/api/map/point/*`
  - 单点导航：`POST /api/map/nav_custom`，支持数据库点位和临时 map 坐标
  - 多点任务 CRUD/执行/暂停/恢复/取消/状态：`/api/map/task/*`、`/api/map/nav_multi/*`
  - ROS1 内部：`move_base` action、`/nav_multi/execute|pause|resume|cancel`、`/nav_multi/status`
  - FastAPI 自动 OpenAPI `/docs`、`/openapi.json`，并注册同源 MCP tools
- container_facts: 一体化镜像包含 Web、FastAPI、内部 rosbridge 和 nav_multi；地图与 SQLite 数据库已有宿主机卷挂载方案。
- product_gaps:
  - 无鉴权、TLS、RBAC、API 版本路径和幂等请求机制。
  - 导航执行未校验点位/任务所属地图是否为当前激活地图。
  - HTTP `next/end/passage` 只有预留包装，当前 ROS nav_multi 节点未注册对应 service。
  - APP 仍存在 `/api/map/nav_multi` 与后端 `/api/map/nav_multi/execute` 的路径契约差异。
  - `action/actionContent` 已入库，但未在 nav_multi 到点后执行。
  - 导航状态为进程内状态，容器重启后不恢复任务。
  - SQLite 仅执行建表 schema，尚无正式迁移/version 管理。
- recommendation: 面向客户冻结 `/api/v1` 北向 API；ROS/rosbridge 作为容器内部实现；外部仅经 80/443 网关访问，并为地图、点位和任务增加 revision、鉴权、审计、幂等和持久化状态。
- forbidden: 未授权不修改接口、数据库 schema、APP、镜像或 Jetson。
