# Context Checkpoint — 2026-09-18 晚：701 容器升级 + 语音容器部署 + 相机映射修正（均已验收）

> 设备事实源：`facts/jetson_profile.yaml` → `jetson.runtime_2026_09_18_701_upgrade`（含 camera_config_2026_09_18）
> 本次结论：`tasks/completed.md` 的 `TASK-2026-09-18-701-CONTAINER-VOICE` 与 `TASK-2026-09-18-701-CAMERA-TOPIC`
> ⚠️ 本文件曾被两个 AI 并发写过；改动前先重读全文，别只追加。

## 刚完成（2026-09-18 16:04–17:00 CST，701 = 192.168.31.135）
- ✅ 免密 sudo 生效：`/etc/sudoers.d/010-jetson-nopasswd`（0440，一行 `jetson ALL=(ALL) NOPASSWD: ALL`，15:55 用户操作）；回滚 `sudo rm` 该文件。
- ✅ 固件三容器 1.0.17 → **1.0.23**；导航 **手工容器 → compose 服务 `scout-nav` + `d360_nav2d:1.2.5`**；语音 **`voice-assistant` 1.0.2**（旧宿主栈已迁移，jetson crontab 0 条）。
- ✅ 验收：5 容器 Up；nav/5011 health 200；门禁通 `[状态] WAIT_WAKE`；`/api/assistant/speak` → `COMPLETED / reply=我在 / speechPlayed=true`。
- ✅ **唤醒词闭环已由用户人耳实测通过**（「小飞小飞」→「我在」）；✅ **重启自愈 PASS**（66s SSH 回、5 容器自起、旧宿主栈未回来、16:22:17 `WAIT_WAKE`、冷启动后 speak played=true）。
- ✅ **相机映射修正（701）**：实测 A=左、B=前、C=右 → compose 的 `scout-nav` 加 `CAMERA_TOPIC=/SLB_CAM_B/compressed`，重建后日志 `camera frame cache started on /SLB_CAM_B/compressed`，nav 实时帧与 CAM_B 实拍同一画面。
- ✅ 执行要点：安装器一律先 `--dry-run`；部署源 `/tmp/d360_deploy-upload`（= Gitee master `0eb79b7`，三方 sha256 一致）；**先停手工 nav 容器再跑 nav 安装器**（否则两容器争 5000、health 被旧容器答 200 → 假成功）。

## 有效事实源 / 红线
- 交付物 = ACR 镜像；推 Git/Gitee 只是开发动作。compose = `/etc/slamibot/system/docker-compose.yml`（现 5 服务），改 tag 后**点名服务** `up -d`。
- **相机映射按机型**：715 = A 前/中、B 左、C 右；**701 = A 左、B 前、C 右** → 701 必须 `CAMERA_TOPIC=/SLB_CAM_B/compressed`（已写进 701 compose 的 environment，`install_2d_nav.sh` 升级只改 image 行、不会覆盖）。禁止硬编码卡号/话题前缀。
- 语音设备：`0d8c:0012` 音箱 + `2208:0001` 六麦 + `lg_speech_serial` 别名；**卡号每次重启会变**（hw:2,0→hw:3,0；ttyUSB8→ttyUSB4）→ 按名字/别名取。
- 红线：不动 PA（`pactl` 观测者效应会造 EBUSY）；测 ALSA 必取 `$?`；USB 分支掉线先查线；`crontab` 必须 `-u jetson`；`docker compose up -d` 会收敛同项目里不一致的容器。
- 其它线（勿重复做）：视频卡/坐标卡已收官（APP 预览 `5be6646` 已切独立 HTTP MJPEG；**点云降采样已取消**）→ 见 `handoff/MJPEG-VIDEO-LINK-TUNE-50PCT-HANDOFF-2026-09-17.md`、`handoff/APP-COLLECTION-PREVIEW-HANDOFF-2026-09-18.md`。

## 未完成 / 下一步
1. ⏳ **`/keyframe` 三格面板顺序**：固件 `cam_topics=B,A,C` 对 715 = 左,前,右；在 701 上呈现为 **前,左,右**。未改（固件红线、镜像两款共用）→ 需用户决策是否做按机型配置。
2. 701 遗留（保留未清，删除需逐次确认）：旧手工 nav 容器 + 12 个历史 stopped `scout-nav-*`、`/home/jetson/voice-old-source-20260918-161711`；`xf_config.yaml` 仍是真实讯飞凭据（开发机）。
3. `d360_deploy/nav2d/install_2d_nav.sh` **第 1 行孤立 `205`**（Gitee 未修；`sudo bash` 调用不受影响）。
4. 语音脚本自验 `chk "旧 crontab 自启已摘除"` 少 `-u` → 假 PASS（未修）。
5. 715：`core`/`ota_web` 仍 1.0.22（compose 已指 1.0.23，下次重启统一）；715 公钥已清空（交付要求）。
6. 挂起：`mttcan` 自加载（冷启动 `can0` 不存在 → 底盘激活永远 NONE）；4G PPP-vs-ECM 通路未确证（勿在交付机上试）。

## 验证状态 / 禁止
- 真机已验证项见 `facts` 的 `acceptance` 与 `camera_config_2026_09_18`；**未做**：旧容器清理、715 复测、`/keyframe` 面板顺序调整。
- 用户快速模式：未跑仓库测试；不得把「已上传/已部署」当成「功能已验证」。
- 待用户决策：出货版是否保留免密 sudo（当前 `jetson` 口令仍是弱口令）。
