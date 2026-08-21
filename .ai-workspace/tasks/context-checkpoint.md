# 最新上下文检查点

- updated: 2026-08-21
- current_focus: BOX 麦克风硬件问题移交同事，任务暂停。
- task: `TASK-2026-08-21-001`
- status: paused_hardware_handoff
- handoff: 同事检查 BOX 硬件、USB 连接/供电、固件及设备枚举；Codex 暂不继续 Jetson 诊断、应用修改或 udev 修改。
- key_facts:
  - 正常 BOX：`arecord -l` 有 `card 3: L6Microphone [ListenGo Circular 6-Microphone]`，并有音频 + CDC 复合 USB 接口。
  - 故障 BOX：缺少 `L6Microphone/ListenGo` 声卡，仅有通用 `USB Audio Device (card 2)`。
  - 故障 BOX：`/dev/lg_speech_serial` 可打开，但通用 USB 音频 WAV 近静音；语音交互程序因找不到 ListenGo 设备退出。
  - 应用的 ListenGo 匹配逻辑暂不修改；正常 BOX 已证明该路径正确。
- unresolved: 故障原因可能是硬件、USB 连接/供电、固件或枚举异常，等待同事结论。
- resume_inputs: 正常/故障 BOX 的 `lsusb -t`、`arecord -l`、`/proc/asound/cards`、设备描述符、硬件检查结果。
- safety: ROS1 CURRENT；不触发 ROS1→ROS2 迁移，不修改业务代码、Jetson、Docker、udev 或接口。
- tests: SKIPPED (task paused and handed off).
- note: 已完成工作区逻辑压缩；不代表删除聊天历史或触发底层上下文清理。
- recovery_order: `AGENTS.md` → 本检查点 → `tasks/current.md` → 相关 facts。
