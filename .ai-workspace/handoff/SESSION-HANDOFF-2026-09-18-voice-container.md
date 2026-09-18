# 会话交接 — 语音助手容器化 + 715 交付清理 + 4G/图传调查（2026-09-18）

> **新会话先读这份，再按需读文末「事实源」列的文件。**
> 本文只写「现在在哪 / 下一步做什么 / 别踩什么」，细节不重复。

---

## 0. 一句话现状

**语音助手已容器化并在 715 上部署验收通过（含唤醒闭环与重启自愈）；715 已完成交付前清理；4G 与图传两条链路已查清（图传已修复并写进装机流程，4G 是客户侧文档）。**

**下一步要做的：** 701 的容器升级 + 701 上部署语音助手容器（**当前被 3 个阻塞挡住，见 §3**）。

---

## 1. 已交付物（可直接引用，不要重新发明）

### 镜像（ACR，**已公开**，客户设备零凭据匿名可拉已验证）

```
registry.cn-shanghai.aliyuncs.com/slamibot/d360_voice_assistant:1.0.2
digest sha256:26cfc05c2843b9ac0bb3d577c3fcc3bfb18b33b20add69ec6d7094e6bd109f7b
arm64 / 595MB / ENTRYPOINT=["/opt/voice/entrypoint.sh"]
```

- ⛔ **1.0.0 作废**：把厂商 demo appid 真值打进了镜像
- ⛔ **1.0.1 作废**：**漏写 `ENTRYPOINT`** → 容器跑基础镜像默认 `/bin/bash`、无 TTY 读 EOF 立刻 `exit 0`（"启动成功却秒退"、5011 永不起、装机脚本 health 超时回滚）
- 已加构建期断言：`Entrypoint 非空` + 值级凭据扫描（构建上下文与镜像内容各扫一次）

### Gitee `d360_deploy`（master 已同步）

| commit | 内容 |
|---|---|
| `abfeab7` | 语音助手改容器化（Dockerfile/entrypoint/tools/一键脚本/音频同步单元），默认 tag 修正为 1.0.2 |
| `a27b70e` `fad6eb7` | README / 客户指南修正 |
| `cd592de` | 删废弃 `voice/supervise_*.sh`；自验兼容 701 容器命名 |
| `0eb79b7` | **图传静态 IP 纳入基础装机**（`net/install_static_ips.sh` + `setup_env.bash` 新第 5 步）+ `net/CUSTOMER-4G-ACTIVATION.md` + `docs/DELIVERY-CLEANUP-CHECKLIST.md` + README |

### 工作区（GitHub，分支 `codex/teleop-pointcloud-low-latency-docs`）

`ce6e58e`（语音这条线）+ `71068cf`（其它未提交记录同步）

---

## 2. 715 现状（**已完成，别重复做**）

| 项 | 状态 |
|---|---|
| 语音助手 | ✅ 容器 `voice-assistant` 运行中（1.0.2），`run_mic` `WAIT_WAKE`，5011 health 200 |
| 唤醒闭环 | ✅ 用户实测「小飞小飞」→ 听到「我在」（走 nav 侧 `tts_cache` 命中） |
| **重启自愈** | ✅ 验证过：重启后容器自己起来、**旧宿主语音栈没回来**（crontab 0 条）、门禁通后自动 `WAIT_WAKE` |
| 宿主单元 | ✅ `slamibot-audio-node-sync.service` active（保导航到点播报） |
| 旧源码 | ✅ 已移出并删除（原 `/home/jetson/voice-old-source-*`） |
| 讯飞凭据 | ✅ 已换成**空模板**（键长度全 0，0600） |
| 值级扫描 | ✅ `NO_CREDENTIAL_VALUES_OK`（8236 文件 × 6 模式） |
| 导航测试残留 | ✅ 地图 504M + 建图产物 328M + `db/captures/*.jpg` 照片 全清 |
| 免密 sudo | ✅ 已删 `/etc/sudoers.d/010-jetson-nopasswd` |
| **SSH 公钥** | ✅ **已全清**（`authorized_keys` 0 字节）→ **我已无法再访问 715** |

### ⚠️ 715 两个待办（我在上下文里已提出，用户未答复）

1. **弱口令**：公钥清空后只剩密码登录，而 `jetson` 口令仍是默认弱口令 → **交付前必须由客户/按客户策略设置强口令，我方不得代设**。已写进 `docs/DELIVERY-CLEANUP-CHECKLIST.md`
2. **图传**：已修好（`eth1` 拿到 `192.168.144.87/24`、`ip neigh` 见 `192.168.144.11 REACHABLE`），但**用户用 APP 实测的结果没回来** —— 若 APP 仍连不上，需要在设备本地排查（我已无 715 访问权限）

---

## 3. 【下一步任务】701 容器升级 + 语音容器部署

### 3.1 当前 701 状态（本会话末实测）

```
容器（**全部落后**）:
  core / firmware-sensors / ota_web → slamibot_d360_firmware:1.0.17
  scout-nav-product-v1.2.2-b2cfd1b-test-20260916 → d360_nav2d:1.2.2     ← 手工起的测试容器，非 compose 管理的 scout-nav
最新版本对照:
  firmware 1.0.23 / d360_nav2d 1.2.5
设备:
  BOX 分支整支不在总线上（无 2208:0001 六麦、无 0d8c:0012 音箱、无 lg_speech_serial）
  → 语音容器会卡在门禁，**验证不了唤醒闭环**；自验第 3/4 项会 FAIL（设备确实不在）
sudo: 需要密码（另一个 AI 只给 715 配了免密）
同事在跑 catkin_make（开发机，可能在用）
```

### 3.2 三个阻塞（必须先解决）

1. **701 免密 sudo**（或用户自己跑）
   安全顺序（照 715 那次的做法，**不要直接改 `/etc/sudoers`**）：写候选 drop-in → `visudo -c -f <候选>` 单独校验 → `install -m 0440 -o root -g root` → `visudo -c` 整体校验 → `sudo -n true` 验证。回滚：`sudo rm /etc/sudoers.d/<file>`
2. **确认同事空出来**（且 701 的 BOX 是否接上、六麦/音箱是否在位）
3. **确认 701 导航容器的目标形态**：现在那个 `scout-nav-product-v1.2.2-...-test-20260916` 是**手工测试容器**；要对齐成 715 那样的 compose 管理 `scout-nav`（服务名 `scout-nav`），还是继续手工容器？**这决定升级方式**

### 3.3 建议执行顺序（每步留可回滚点）

```
0) 读 /etc/slamibot/system/docker-compose.yml 与 docker ps，确认实际形态
1) 备份 compose + crontab
2) 记录回滚点（镜像 tag、容器名、compose 路径）
3) 固件三容器升级（改 compose 的 image → docker compose up -d core firmware-sensors ota_web）
   ⚠️ 注意：compose up 会**顺带重建与 compose 不一致的容器**（今天在 715 上 core 被 1.0.22→1.0.23 就是这个）
4) 导航：新 tag 1.2.5（先 docker pull 再改 compose，别先改后拉 —— 715 踩过时钟/拉取顺序的坑）
5) 语音：装 net/install_static_ips.sh? 不 —— 语音是
   curl -fsSL -o /tmp/install_voice_assistant.sh https://gitee.com/electech6/d360_deploy/raw/master/voice/install_voice_assistant.sh
   sudo bash /tmp/install_voice_assistant.sh --dry-run     # 先看计划
   sudo bash /tmp/install_voice_assistant.sh                # 正式装（默认拉 1.0.2）
6) 装后自验 8 项；**唤醒闭环必须等 BOX 接上后测**
```

---

## 4. 本会话踩过的坑（**照这个顺序查，能省几小时**）

1. **观测者效应（代价最大的一次）**：我用 `pactl` 查 PulseAudio 状态，而**任何 PA 客户端都会把 sink 从 `SUSPENDED` 唤醒成 `IDLE`** → PA 占住 USB 声卡 → 我下一次 `aplay` 就 `EBUSY`。我据此误判"PA 占卡"、还提了要 mask PA 的建议 —— **其实是自己造的故障**。
   → **测 ALSA 播放时不要碰 `pactl`**；要判链路先看 `lsusb -t` + `/proc/asound/cards` 是否稳定在位。
2. **必须取退出码**：`aplay` 打印 `Playing raw data ...` 只是启动提示，**不代表打开成功**。不带 `rc=$?` 的测试会给出错误结论。
3. **USB 分支掉线**是 BOX 相关故障的常见根因（本会话两次）：判据是 `lsusb -t` 里分支消失 + `Device not responding to setup address` + **只跑 `full-speed`(12M) 而非 `high-speed`(480M)**。**先查线**，别查驱动。详见 `known-issues/box-usb-branch-drop-and-can0-reattach-2026-09-17.md` §6。
4. **`[ -n "$x" ] && { ...; }` 在 `set -e` 下会静默杀死整个脚本**（条件不成立时）。装机脚本三次都死在"无进程可杀"处，靠 `set -x` 才定位。**用 `if`**。
5. **`sudo` 下 `crontab -l` 读的是 root 的 crontab**，删不到 `jetson` 的旧自启行 → 必须 `crontab -u "$TARGET_USER"`。
6. **Docker 单文件 bind mount 的源文件不存在时会建同名目录** → 挂载失败。所以清理凭据时是"**换空模板**"而非删除文件。
7. **装机脚本 SSH 一断就被 SIGHUP 杀掉** → 远程跑长脚本要 `nohup ... > log 2>&1 < /dev/null &`，并落盘日志再读。
8. **ACP 新仓库默认私有**：`d360_nav2d` 匿名可拉、新推的 `d360_voice_assistant` 不行 —— 需在控制台设公开（用户已设好）。判据用 `docker manifest inspect`（`/v2/.../tags/list` 匿名必 401，别用它判断）。

---

## 5. 未确证 / 待决策（**不要当成已知**）

1. **4G 到底走哪条通路：未确证。** 我在 715 上观察到 `usb1` / `192.168.225.x` / metric 20102，但工作区事实源（`facts/jetson_profile.yaml` 的 `cat4`，**CONFIRMED 2026-09-01**）记录 D360 的 EC20F 走 **PPP `ppp0`（metric 20900, `10.8.72.41/32`, NM 连接 `China-Mobile-4G`, APN `cmnet`）**，并明确写「**禁止硬编码 usb1 或套用 EC800K ECM 流程**」、`usbnet_mode: 0`。
   → 我观察到的更像 **BOX（EG25/EC800K，RNDIS/ECM）** 的记录。`net/CUSTOMER-4G-ACTIVATION.md` 已把 `AT+QCFG="usbnet"` 等标为 `NEEDS_CONFIRMATION`，并写明「**交付设备不要做这个实验，可能弄坏已确证的 ppp0**」。
   → **建议在一台非交付设备上先核实**再更新文档。
2. **仓库自己在"谁拉起 4G"上前后不一致**：`77-mm-ignore-usb0.rules` 注释说"自定义 PPP 脚本"，facts 说 ModemManager/NetworkManager 的 PPP。
3. **离线 TTS（可选）**：现场无网时"识别已离线（本地 sherpa-onnx）、只有出声需要讯飞"。若要做"无网也能出声"，方向是 **`sherpa-onnx` 自带 TTS**（与现用识别引擎同源、可复用依赖），**不是** vosk（vosk 只做 ASR，已确认是废弃 demo 并删除）。
4. **脚本自验第 6 项未在真机复验**（那处 `crontab -u` 修复只做了语法+审阅）。
5. **图传装机脚本未在真机跑过**（`net/install_static_ips.sh`，只有 stub `--dry-run` 通过）；现场跑完以 `ip neigh | grep 192.168.144` 出 `REACHABLE` 为判据。

---

## 6. 事实源（按需读，**不要默认全读**）

| 主题 | 文件 |
|---|---|
| 语音容器化全部细节（方案/P0 实测/验收/红线/踩坑） | `tasks/voice-containerization-plan-2026-09-18.md` |
| 短检查点（恢复用） | `tasks/context-checkpoint.md` |
| BOX USB 分支掉线（含 2026-09-18 复发与教训） | `known-issues/box-usb-branch-drop-and-can0-reattach-2026-09-17.md` |
| 701 六麦/音箱未枚举（另一类，BOO 拓扑漂移） | `known-issues/701-box-usb-topology-drift-voice-devices-absent-2026-09-18.md` |
| 凭据审计（701 现网真实凭据 / 权限偏差 / demo 账号扩散） | `knowledge/715-shipping-credential-audit-2026-09-17.md` |
| 板内语音与辅助服务盘点（vosk 已改为"已删除"） | `knowledge/d360-voice-and-services.md` |
| 4G 通路事实（PPP vs ECM 之争的原始记录） | `facts/jetson_profile.yaml` 的 `cat4` 块 |
| 交付前清理步骤 | Gitee `d360_deploy/docs/DELIVERY-CLEANUP-CHECKLIST.md` |
| 4G 客户激活 | Gitee `d360_deploy/net/CUSTOMER-4G-ACTIVATION.md` |

---

## 7. 权限与边界（新会话必须知道）

- **715 已无法用密钥登录**（公钥被清空，这是交付要求）→ 715 上的事只能用户在设备本地做，或先用密码登录后加回公钥
- **701 的 sudo 要密码**；未拿到免密或用户代跑前，701 的容器升级做不了
- **Jetson 默认只读**；BUILD/DEPLOY 需要用户在当前任务中明确授权
- 删除、重启、改系统配置、清理磁盘等属 DANGEROUS，**逐次人工确认**
