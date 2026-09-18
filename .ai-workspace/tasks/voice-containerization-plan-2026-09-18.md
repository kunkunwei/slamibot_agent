# 701 语音识别程序容器化部署方案（2026-09-18）

- 状态：**needs_confirmation**（方案已成形，等用户决策 4 项 + 701 开机授权）
- 触发：用户 2026-09-18 提出「701 语音识别程序有必要做成容器化部署」
- 只读调查，**未改任何业务代码、未碰设备、未构建镜像**

## 1. 现状：语音跑在宿主，不在任何镜像里

三块资产（= `install_voice_assistant.sh` 装的东西 = crontab 拉起的东西）：

| 宿主路径 | 内容 | 体积 |
|---|---|---|
| `/home/jetson/run_mic_sherpa` | `run_mic.py`(770 行)、`assistant_client.py`、`cmd_matcher.py`、`run_mic_bias.py`、`.venv`、`models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20/` | 458M（.venv 118M + models 341M） |
| `/home/jetson/assistant_runtime` | `supervise_sherpa.sh`、`supervise_xf_gateway.sh`、`xf_gateway/`(5011)、`logs/`、flock 锁 | 0.8M |
| `/home/jetson/xf_chat_standalone` | `spark_api.py`、`serial_reader.py`、`intent_router.py`、`xf_config.yaml`(凭据 0600) | 0.1M |

自启 = `jetson` 用户 crontab 两条 `@reboot` + `flock`（`tmp/voice-715-deploy/crontab.jetson`；脚本侧 `tmp/d360_deploy/voice/install_voice_assistant.sh:49-51`）。

**701 与 715 同构**，只差：① 导航容器名 `scout-nav-product-*` vs `scout-nav`（`tmp/d360_deploy/voice/supervise_sherpa.sh:9` 的 `resolve_container()` 兼容两者）；② 701 udev 规则手工加过 `lg_speech_serial`（`known-issues/715-serial-ports-hung-status-page-empty-2026-09-17.md:66,90`）。
701 确认有这两条 crontab（`tasks/current.md:1554`，2026-09-16 只读排查）；**701 语音的 PID/端口/日志从未实机采集**（`NEEDS_CONFIRMATION`）。

## 2. 容器化必须保持的隐式契约

- 语音 → nav `127.0.0.1:5000`：`/health`、`/api/assistant/{turn,speak,status,jobs/{id}}`（`status` **每 250ms**，`supervise_sherpa.sh:81`）、`/api/voice/{words,intent}`。
- nav → 语音：**UDP `127.0.0.1:5012`** —— `run_mic.py` 是 ListenGo 采集设备的**唯一持有者**，喊话时把已采集 PCM 转发给 nav，nav 不再自己 `arecord`（`tmp/nav-50pct/src/nav_api/fastapi_service/audio.py:70-74`）。
- nav → `127.0.0.1:5011/v1/synthesize`（到点播报）；5011 不可用时回退容器内 `tts_cache/*.pcm`。
- 以上全部依赖 `network_mode: host`（`tmp/d360_deploy/nav2d/install_2d_nav.sh:104`）。**语音容器必须继续用 host 网络。**

## 3. 两个必须先处理的坑

### 3.1 `docker exec mknod /dev/snd` hack 与 nav 播报的连带关系
`supervise_sherpa.sh:23-50`：nav 容器启动时快照 `/dev/snd`，而六麦阵列/USB 声卡是开机后几十秒到**最坏 18 分钟**才出现（`knowledge/d360-cold-boot-stability-analysis-2026-09-17.md:19,96`）→ nav 容器里永远看不到节点，`aplay` 静默无声。宿主每 5s 用 `docker exec` 补造节点。
**删掉宿主 supervisor 会连带打断 nav 的 TTS 播报**，所以必须把这段抽成独立宿主 systemd 单元（见 §5.4）。

### 3.2 凭据泄漏（安全项）—— ✅ 2026-09-18 已清理
`tmp/voice-715-deploy/voice-assets.tar.gz`（346M，2026-09-17 13:30 快照）曾是**清理前**的产物，包内同时含：
- `xf_chat_standalone/xf_config.yaml`：厂商 demo 账号（注释）+ **701 真实账号活动键**（appid 8 / key 32 / secret 32）
- `xf_chat_standalone/README.md:51-53`：厂商 demo 账号明文

**已处置**：流式重建资产包（明文不落盘）→ 整包丢弃 `xf_config.yaml`（安装器本就 `--exclude` 它；权威副本在 `.ai-workspace/secrets/CREDENTIALS.md`，已核验 3 个值均在其中）；`README.md` 三处 demo 值 → 占位符。复核：成员 1495→1494、关键文件/软链/模型齐全、6 条模式独立复扫 **0 残留**、原件不留备份。
工具 `tmp/voice-715-deploy/sanitize_voice_assets.py`（fail-closed）；明文模式只存 `.ai-workspace/secrets/voice-credential-patterns.txt`（gitignore）。全工作区终扫 4541 个文本文件 **0 命中**；两套值在 d360_deploy(→Gitee) 与工作区(→GitHub) 的历史/工作树均 0 命中；`voice-assets*.tar.gz` 已加入 `.gitignore`（此前未忽略）。详见 `knowledge/715-shipping-credential-audit-2026-09-17.md` §一.3。

**构建输入要求（仍须执行）**：以 sanitize 后的包为输入 + `.dockerignore` + 构建期断言扫描 + 验收期 `find / -name xf_config.yaml` 必须为空。
⚠️ **仍未解决**：701 的 `/home/jetson` 下 498 个文件仍含该 demo 账号，唯一可靠做法是**到讯飞控制台重置该账号密钥**。

## 4. 目标与范围

**目标**：把 701 上 crontab+flock 拉起的宿主语音链路，改成**一个 ACR 镜像 + 一个 compose 服务**；701 验证通过后推广到 715/新机型。
**成功判据**：701 删掉两条 crontab、删掉宿主 supervisor 后，唤醒/离线识别/对话回复/到点播报/nav 喊话回传全部照常；`docker compose up -d voice-assistant` 一条命令安装升级；重启自动恢复。

**在范围**：`run_mic_sherpa`（sherpa-onnx 唤醒+离线 ASR）+ `xf_gateway`(5011) + `xf_chat_standalone`。
**不在范围**：`/home/jetson/vosk`（遗留，不在自启链路上）、nav 镜像/nav compose、固件、rosbridge、OAK/`/keyframe`（§6 红线）。

## 5. 方案（推荐：自包含镜像）

### 5.1 镜像
`registry.cn-shanghai.aliyuncs.com/slamibot/d360_voice_assistant:1.0.0`

- base `arm64v8/ubuntu:20.04`（对齐 701 的 Jetson Ubuntu 20.04 / Python 3.8）。
- 内容：`run_mic_sherpa` 全部源码 + `models/`(341M) + `xf_gateway/` + `xf_chat_standalone` 源码（**排除 `xf_config.yaml`**）+ 容器版 entrypoint + `alsa-utils`/`libportaudio2`/`python3-yaml`。
- 依赖走**离线 wheelhouse**：701 上 `pip download -r requirements.txt -d wheelhouse`，构建时 `pip install --no-index --find-links=wheelhouse`。**不搬宿主 `.venv`**（shebang 绑死 `/home/jetson/...`）。
- 分层：`models/` 最下，代码层在上 → 改代码只重推小层；后续小改用 `Dockerfile.voice-overlay`（仿 `tmp/nav-50pct/Dockerfile.video-link-overlay`）。
- 构建期断言（照既有 overlay 约定）：镜像内无 `xf_config.yaml`、全部 `.py` `py_compile`、`models/` 关键 onnx 存在、entrypoint 可执行。

**为什么模型进镜像**：交付模型是「设备上的一切都靠脚本从 ACR 拉镜像」（`handoff/MJPEG-VIDEO-LINK-TUNE-50PCT-HANDOFF-2026-09-17.md:46-49`），而 341M 模型 + `.venv` **不在任何 Git 仓库**，导致 `tmp/d360_deploy/voice/README.md:83-89` 记录「面向客户的资产分发渠道（私有 release/网盘/U 盘）**尚未决定**」。模型进镜像 = 该悬案消失，装机回到一条 `docker pull`。代价：镜像约 600–700M，首次拉取慢（一次性）。

### 5.2 compose 服务块（追加到 `/etc/slamibot/system/docker-compose.yml`）
```yaml
  voice-assistant:
    image: registry.cn-shanghai.aliyuncs.com/slamibot/d360_voice_assistant:1.0.0
    container_name: voice-assistant
    network_mode: host
    privileged: true
    restart: unless-stopped
    volumes:
      - /dev:/dev                                   # 整目录挂：晚出现的 /dev/snd、/dev/lg_speech_serial 自动可见
      - /home/jetson/xf_chat_standalone/xf_config.yaml:/etc/slamibot/voice/xf_config.yaml:ro
      - /etc/localtime:/etc/localtime:ro
    depends_on:
      - core
```
- `/dev:/dev` 与 `core`/`firmware-sensors` 既有写法一致（`tmp/d360_deploy/docker-compose.yml:13`）。**这是替代 mknod hack 的关键**：bind mount 目录会传播新出现的设备节点。
- 凭据保持宿主原路径，只额外只读挂载 → 不动客户指南与凭据搬运脚本。
- `restart: unless-stopped` + 容器内门禁循环取代 `@reboot`+`flock`。

### 5.3 容器内 entrypoint（取代两个 supervisor）
1. 后台起 `xf_gateway`（`xf_assistant_gateway.py --host 127.0.0.1 --port 5011`，stdlib-only，只需 `websocket-client`+`PyYAML`）。
2. 等自身 `5011/health` 200（上限 20s，对齐 `install_voice_assistant.sh:634`）。
3. 门禁 `until` 循环（照 `supervise_sherpa.sh:67-76`，去掉 `docker exec`/`mknod`）：`/dev/lg_speech_serial` + `arecord -l` 见 ListenGo + `aplay -l` 见 USB Audio Device + `127.0.0.1:5000/health` → 2s 重试。
4. `run_mic.py --device-name "ListenGo Circular 6-Microphone" --server http://127.0.0.1:5000 --serial-port /dev/lg_speech_serial --status-interval 0.25`，退出 5s 重试（保留 fail-closed：串口不健康 → `DEGRADED_NO_WAKE`）。
5. USB 音箱音量自愈 `amixer -c Device sset Speaker 46% unmute`（`supervise_sherpa.sh:44-49`）**归语音容器**。
6. 日志走 stdout（`docker logs voice-assistant`）。**容器里 cron 不跑**，故必须换掉 crontab。

### 5.4 宿主侧必须保留的补丁：音频节点同步独立化
- 新增 `slamibot-audio-node-sync.service`（systemd，`Restart=always`，5s 循环）= 现 `supervise_sherpa.sh:23-50` 去掉音量那半段。
- **不碰 nav 容器配置**（nav compose 由 `install_2d_nav.sh` 管理、已存在只改 `image:` 一行，改它属 nav 侧授权范围）。
- 后续可选（不在本方案）：nav compose 加 `- /dev/snd:/dev/snd` bind mount 可彻底替代 mknod 循环。
- 顺带满足运维 runbook 的既有诉求（`快速修复指南/容器重启后的问题/2D导航新容器语音唤醒与到点播报排查.md:1094-1110`：纳入 systemd 而非长期依赖 crontab）。

### 5.5 安装脚本
新增 `d360_deploy/voice/install_voice_container.sh`，照 `install_2d_nav.sh` 结构：
`--dry-run` → 前置（root/docker/compose 文件/`core` 在跑）→ `docker pull` → 备份 compose → Python heredoc 最小插入服务块（已存在只改 `image:`）→ `docker compose config` 校验（失败还原）→ `up -d voice-assistant` → 轮询 `5011/health`，超时回滚 → 装 systemd 音频同步单元 → **移除**两条 `SLAMIBOT_ASSISTANT_AUTOSTART` crontab → 自验。
旧 `install_voice_assistant.sh` 保留并标 deprecated（回滚路径）。

## 6. 分阶段实施

- **P0 只读核实（需 701 开机 + SSH 授权）**：crontab 两条原文、`.venv/bin/python -V` + `pip freeze`、`models/` 清单与 md5、`/dev/lg_speech_serial` 实际指向、`arecord -l`/`aplay -l` 卡名、容器名、`/etc/slamibot/system/docker-compose.yml` 现状、`docker images`、5011/5000 监听、`sherpa.log` 尾部。**缺任一项不动手。**
- **P1 构建输入 sanitize（阻塞性）**：见 §3.2。
- **P2 写 Dockerfile / entrypoint / .dockerignore / wheelhouse**，在 701 上原生 aarch64 构建（Windows/QEMU 构建历史失败过）。
- **P3 一次性测试容器**：**两实例会争 ListenGo 采集**，故测试容器用 `voice-assistant-test` + `docker run --rm`、不写 compose；验证顺序 = 设备可见性 → 5011 → 能否打开声卡 → 唤醒日志；做完整闭环前先精确 `kill` 宿主那条 sherpa 进程（不用 `pkill`），测完立即恢复。
- **P4 推 ACR（tag 1.0.0，不覆盖已发布 tag）+ 装机脚本 + 701 切换**：旧宿主资产**不删**，只停 crontab → 保留一键回滚。
- **P5 验收**（§7）。
- **P6 文档同步**：`voice/README.md`、`快速修复指南/.../2D导航新容器语音唤醒与到点播报排查.md`（§6 整节重写；`:278` 的 `grep '^CONTAINER='` 早已失效）、`knowledge/d360-voice-and-services.md`（补 5012 UDP 单占者契约）、`procedures/d360-2d-nav-new-device-deploy-2026-09-16.md:102`、`facts/jetson_profile.yaml:324-331`、`tasks/context-checkpoint.md`。
- **P7 推广 715/新机型**（本次不执行；容器名差异因容器自带 `container_name` 而消失）。

## 7. 验收清单（701）

- [ ] `docker ps` 有 `voice-assistant`（`unless-stopped`）；两条语音 crontab 已移除；无重复 `run_mic`
- [ ] 日志到 `WAIT_WAKE`
- [ ] 唤醒「小飞小飞」→「我在」→ 命令词 → nav 收到 `/api/voice/intent`
- [ ] 到点播报出声（5011 `/v1/synthesize`）
- [ ] APP 喊话回传正常（UDP 5012）
- [ ] `5011/health` 200、`5000/health` 200、`docker exec voice-assistant arecord -l` 见 ListenGo
- [ ] nav 容器内 `aplay -l` 见 USB Audio Device（音频同步单元在跑）
- [ ] 冷启动自动恢复，**含六麦模块分钟级才出现**的场景
- [ ] 镜像内 `find / -name xf_config.yaml` 为空；`docker history` 无凭据层
- [ ] 回滚演练：恢复两条 crontab → 唤醒恢复正常

## 8. 红线与风险

**不动**：nav 镜像、nav compose（除 §5.4 明确项）、固件镜像、rosbridge、OAK/`/keyframe`（§6 红线）、OAK `setQuality`、现有宿主资产（P4 前）、Git 历史。

| 风险 | 处理 |
|---|---|
| 六麦模块最坏 18 分钟才出现 | `/dev:/dev` 整目录挂 + 门禁循环，不靠启动快照 |
| 两实例争 ListenGo 采集 | P3 前先停宿主 sherpa；容器化后宿主不再有 `run_mic` |
| `privileged: true` 扩大攻击面 | 与既有容器口径一致；凭据只读挂载 |
| 凭据进镜像层 | P1 sanitize + `.dockerignore` + 构建期断言 + 验收 `find` |
| 删宿主 supervisor 打断 nav 播报 | §5.4 必须先落地并验证 |
| `depends_on: [core]` 只是顺序非健康等待 | 真正保证是容器内 entrypoint 门禁 |
| 镜像 600–700M 首次拉取慢 | 一次性；分层 + overlay 保住后续升级速度 |
| 语音与 nav 争 ALSA | 划分不变（run_mic 独占采集、nav 独占播放）；`amixer` 归语音容器 |

## 9. 决策状态

**已定**：
- ✅ 架构：**独立镜像**（导航款设备配 scout-nav + voice-assistant 两个容器）——用户 2026-09-18 明确
- ✅ 镜像名与版本：`d360_voice_assistant:1.0.0`——用户 2026-09-18 确认
- ✅ 含明文凭据的资产包：**已清理**（流式重建 + 原件不留备份），见 §3.2

**仍待决策**：
1. `install_voice_assistant.sh` 原地改造还是新增容器版脚本？（建议新增 + 旧版标 deprecated）
2. `/home/jetson/vosk` 是否一并容器化？（建议不在本次范围）
3. 语音容器是否保留「到点播报」`tts_cache` 兜底？（现由 nav 容器持有，建议不动）
4. 设备切换授权（P3–P5）：是否现在做，以及是否先处理 701 的 BOX/USB 枚举问题

## 10. 相关先例

- **产品设计文档早就规划过语音进容器**：`tmp/nav-50pct/src/nav_api/docs/superpowers/specs/2026-07-31-box-remote-voice-design.md:95-101` ——「d360-voice 进程（框架容器运行，Phase 1+）… 引擎与 nav_api 完全解耦，崩溃不影响导航」；模型挂 volume 不进镜像。实际落地却走了宿主 crontab，本次是把设计拉回来。
- 产品线口径（`tasks/context-checkpoint.md:63`）：基础款 = core/firmware-sensors/ota_web 三容器、**无导航无语音**；导航款 = 基础款 + scout-nav + 语音 → 语音必须**独立镜像**，不塞 nav 镜像。
- ACR 上目前**没有任何语音镜像**，工作区无语音 `docker build/push` 记录。

## 11. P0 只读核实结果（2026-09-18 10:10 实测，701 @192.168.31.135）

**宿主语音栈确认在线**（与 715 同构）：
- crontab 就是那两条 `@reboot` + flock（逐字一致）
- 进程：`flock` 879/881、`supervise_xf_gateway.sh` 880、`supervise_sherpa.sh` 882/887、`xf_assistant_gateway.py` PID 886 监听 `127.0.0.1:5011`、`run_mic.py` PID 415850（`etime` 44:26，开机 1h18m 后由门禁拉起，与"等设备"设计吻合）
- 端口：`0.0.0.0:5000`（nav）、`127.0.0.1:5011`（网关）；**无 UDP 5012 监听**（仅喊话会话期才起，符合预期）
- 无任何语音相关 systemd 单元（只有 `slamibot-wifi-policy`）→ 证实 §5.4 那个新单元确实要建

**运行时与依赖（决定镜像 base 与 pin）**：
- `.venv` = **Python 3.8.10**；`pip freeze`：`sherpa-onnx==1.13.6`、`sherpa-onnx-core==1.13.6`、`numpy==1.24.4`、`sounddevice==0.5.6`、`pyserial==3.5`（+cffi/pycparser）
- 系统 `python3` = 3.8.10，`yaml` / `websocket-client` 均可导入
- Docker 28.1.1、Compose v2.35.1；`~/.docker/config.json` 存在（**ACR 登录已配**）
- 磁盘 54G 可用、内存 9.4G 可用

**路径解析（决定容器内布局与凭据挂载点）**：
- `run_mic.py:33-38`：`SCRIPT_DIR = dirname(abspath(__file__))`；`DEFAULT_MODEL_DIR = SCRIPT_DIR/models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20` → **模型在模型名子目录下**，容器内保持同结构即可，无需改代码
- `run_mic.py:32`：`DEFAULT_PCM_UDP_TARGET = os.environ.get("RUN_MIC_PCM_UDP_TARGET", "127.0.0.1:5012")` → UDP 回传可环境变量覆盖
- `spark_api.py:61-102` 配置查找顺序：ROS2 share（无 ROS 跳过）→ **`script_dir/xf_config.yaml`（优先）** → `../config/` → `cwd/` → **环境变量 `SPARK_APP_ID`/`SPARK_API_KEY`/`SPARK_API_SECRET` 覆盖一切**
  → 容器内凭据用**单文件只读挂载到 `script_dir/xf_config.yaml`**，不动代码、不把凭据放进 compose/environment
- `spark_api.py:33-36`：`ament_index_python` 在 `try/except ImportError` 内 → **容器完全不需要 ROS**
- `words_local.txt` / `hotwords_bias.txt` 只被 `run_mic_bias.py` 用（crontab 跑的是 `run_mic.py`）

**依赖裁剪结论**：容器只需 `sherpa-onnx` / `sounddevice` / `numpy` / `pyserial` / `websocket-client` / `PyYAML`；**不需要 ROS1、ROS2、PyAudio**（`pyaudio`/`rospy`/`std_msgs` 只出现在未运行的 `xf_mic_chat_standalone.py` / `robot_cmd_publisher.py` 里）。

**701 资产与 715 的差异（构建白名单依据）**：`assistant_runtime` 37M（含 `backups/`）、`xf_chat_standalone` 516K（含 `D360(1).pdf`、`.pytest_cache/`、`move/`）——这些都**不进镜像**。

## 12. 交付物（2026-09-18）

- 镜像：`registry.cn-shanghai.aliyuncs.com/slamibot/d360_voice_assistant:1.0.0`（名字与版本号用户已确认）
- 构建产物（`tmp/d360_deploy/voice/`）：`Dockerfile`、`entrypoint.sh`、`.dockerignore`、`tools/check_no_credentials.py`、`build_and_push.sh`
- 宿主前置件（切容器前必须先装，否则 nav 播报静默）：`audio-node-sync.sh` + `slamibot-audio-node-sync.service`
- 构建必须在 aarch64 原生机（701）上做；构建上下文由 `build_and_push.sh` 从设备现网资产现场装配（模型不在任何 Git 仓库，这样免传 458M 且与设备运行物逐字节同源）

## 13. 交付完成：镜像已构建并推送 ACR（2026-09-18 10:45）

**当前有效 tag（用它）**：

```
registry.cn-shanghai.aliyuncs.com/slamibot/d360_voice_assistant:1.0.1
digest  sha256:c495c8b094ecaf7e1ca07cfe78d76bc005739d902f7651bfcc0bc9de5dd1724a
arch=arm64   595MB   构建源 /home/jetson/voice-image-src
```

**⛔ `1.0.0` 已作废，禁止使用**：digest `sha256:384636e7902d0f56cb6d3e1f1332f09932e32e7510db6d86a4445839903e0509`。
它把**厂商 demo appid 明文**打进了镜像（`/opt/voice/tools/check_no_credentials.py` 的 docstring 里我拿真值当示例）——已用值级扫描复现命中（退出码 1）。按「不覆盖已发布 tag」规矩保留 tag 以便追溯，但装机脚本默认值必须写 **1.0.1**。

> 这次是**门禁的自我证明**：形态检查器漏掉了它（裸值写在文档句子中间不在行尾），值级扫描抓到了。因此门禁已加固为「值级精确扫描 = 权威 + 形态检查器 = 辅助」。

**构建期自证全过**：`VOICE_IMAGE_ASSERTIONS_OK`（资产在位 / 模型目录名与 `run_mic.py` 的 `DEFAULT_MODEL_DIR` 一致 / 依赖可导入 / py_compile / 凭据形态扫描 / 镜像内无 `xf_config.yaml`）；构建上下文值级扫描 21 文件 ×6 模式 `NO_CREDENTIAL_VALUES_OK`；**镜像内容值级扫描 29 文件 ×6 模式 `NO_CREDENTIAL_VALUES_OK`**。

**容器内实机验证**（`tools/verify_in_container.sh`，`--network host --privileged -v /dev:/dev`）：

| 轮次 | 结果 |
|---|---|
| A 带凭据挂载（模拟正式运行） | **PASS=15 FAIL=0 BLOCKED=3**；凭据从挂载配置正确载入（len 8/32/32）；`/dev/snd` **48 个节点与宿主完全一致**；nav:5000 可达；网关在备用端口 `/health` 200 |
| B 不挂凭据（降级模式） | **PASS=16 FAIL=0 BLOCKED=3**；`NO_PLAINTEXT_CREDENTIALS_OK` → 镜像自身不含凭据 |

3 项 BLOCKED **全部是设备未枚举**，与容器无关 → `known-issues/701-box-usb-topology-drift-voice-devices-absent-2026-09-18.md`。

**关键设计验证通过**：凭据按 `script_dir/xf_config.yaml` 单文件只读挂载即被 `spark_api` 采用（无需改代码）；`/dev:/dev` 整目录挂载确实传播全部 ALSA 节点；`/proc/asound` 在 `privileged` 下可见（无需额外挂载，且 runc 会拒绝把 `/proc/asound` 作为 bind 挂载）。

**踩过的坑（已修，值得记）**：
1. 模型在 `models/<模型名>/` 子目录下，断言最初写成 `models/*.onnx` → 前置检查拦住（fail-closed 生效）。
2. 凭据检查器首版把 `self.api_secret = api_secret or API_SECRET` 当凭据值 → **3 处误报挡住构建**。修法：`.py` 只认**带引号的字面量**，配置/文档才允许裸值；并补 `re.IGNORECASE`（否则漏掉大写 `API_KEY = "..."`）。已做反向对照：真实资产 PASS、5 种注入形态全部抓到、占位符无误报。
3. `dash` 的 `command -v a b c` **只处理第一个参数**，自证里写成多参数等于没查 → 改为逐个查。
4. 拿 `/home/jetson/xf_chat_standalone` **现网目录**做凭据正例测试是错的——那里**本来就该**有真实凭据（哈希比对确认是 701 真实账号 8/32/32）。正例必须扫**装配后的构建上下文**。
5. **我自己把厂商 demo appid 真值写进了检查器的 docstring 当示例**，并打进了 1.0.0 镜像。形态检查器抓不到（裸值不在行尾），是**值级扫描**抓到的。→ 门禁已加固：`tools/scan_credential_values.py`（值级精确 = 权威）+ `check_no_credentials.py`（形态 = 辅助），构建上下文与镜像内容各扫一次；`build_and_push.sh --patterns` 指向 701 上 `0600` 的 `/home/jetson/.voice-cred-patterns`。**教训：任何示例、文档、注释都不许用真值。**

**未做（等授权）**：设备切换（P3–P5）。宿主语音栈**原封未动**——crontab 两条、supervise/flock/网关进程全在，没有 `voice-assistant` 容器在跑。

**切换前必须先落的两件事**：
1. 宿主 `slamibot-audio-node-sync.service` + `audio-node-sync.sh`（否则 nav 到点播报静默，见 §2.4）。
2. 装容器版装机脚本（compose 服务块 + 摘除两条 crontab），并扩展 `install_2d_nav.sh` 的收敛逻辑——注意它现在「已存在只改 `image:` 一行」，**不会**补 `volumes`，而语音服务块需要 `/dev:/dev` 与凭据挂载（新建服务块走"最小插入"路径没这个问题）。

## 14. 设备侧遗留物（701）

- `/home/jetson/voice-image-src/`（构建配方 4 文件 + tools/2 个脚本，非机密）
- `/home/jetson/voice-image-build/`（341M 装配后的构建上下文，可删；里面**不含**凭据）
- 建议保留 `voice-image-src`（重推镜像要用），`voice-image-build` 可随时由 `build_and_push.sh` 重建
