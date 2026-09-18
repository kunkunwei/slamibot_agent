# Context Checkpoint — 2026-09-18 晚：701 升级+语音容器已完成；源码上云核对与冗余备份清理完成

> 设备事实源：`facts/jetson_profile.yaml` → `jetson.runtime_2026_09_18_701_upgrade`（含 camera_config / cloud_sync / cleanup）
> 结论记录：`tasks/completed.md` 的 `TASK-2026-09-18-701-CONTAINER-VOICE` / `-CAMERA-TOPIC` / `-CLOUD-SYNC-AND-CLEANUP`
> ⚠️ 本文件曾被两个 AI 并发写过；改动前先重读全文，别只追加。

## 刚完成（2026-09-18 16:04–17:55 CST，701 = 192.168.31.135）
- ✅ 免密 sudo 生效：`/etc/sudoers.d/010-jetson-nopasswd`（0440，`jetson ALL=(ALL) NOPASSWD: ALL`，15:55 用户操作）；回滚 `sudo rm` 该文件。
- ✅ 固件三容器 1.0.17 → **1.0.23**；导航 **手工容器 → compose 服务 `scout-nav` + `d360_nav2d:1.2.5`**；语音 **`voice-assistant` 1.0.2**（旧宿主栈已迁移，jetson crontab 0 条）。
- ✅ 验收：5 容器 Up；nav/5011 health 200；门禁通 `[状态] WAIT_WAKE`；`/api/assistant/speak` → `COMPLETED / reply=我在 / speechPlayed=true`；**唤醒词「小飞小飞」→「我在」用户人耳实测通过**；**重启自愈 PASS**（66s 回、5 容器自起、旧宿主栈未回来）。
- ✅ **相机映射修正**：701 实测 A=左/B=前/C=右 → compose 的 `scout-nav` 加 `CAMERA_TOPIC=/SLB_CAM_B/compressed`，nav 实时帧与 CAM_B 实拍一致。
- ✅ **源码上云核对**：nav 仓 `jetson/0826` == `origin/jetson/0826` ✓；语音 `run_mic_sherpa` main == origin/main ✓；框架仓 == `cloud/main` ✓；`kn_nav` == `cloud/master` ✓。
- ✅ **冗余备份清理（约 1.0G）**：删 `voice-old-source-20260918-161711`、`.codex-stage`、`nav-diagnostics-web-deploy-*`、`assistant-deploy-20260828-*`、`docker-entrypoint.sh.bak-*`；删前抢救孤立文件到工作区 `.ai-workspace/tmp/701-voice-orphans-rescued-20260918/`。

## 有效事实源 / 红线
- 交付物 = ACR 镜像；推 Git/Gitee 只是开发动作。compose = `/etc/slamibot/system/docker-compose.yml`（现 5 服务），改 tag 后**点名服务** `up -d`。
- **相机映射按机型**：715 = A 前/中、B 左、C 右；**701 = A 左、B 前、C 右** → 701 必须 `CAMERA_TOPIC=/SLB_CAM_B/compressed`（已写进 701 compose 的 environment；`install_2d_nav.sh` 升级只改 image 行不会覆盖）。
- 语音设备：`0d8c:0012` 音箱 + `2208:0001` 六麦 + `lg_speech_serial` 别名；**卡号每次重启会变**（hw:2,0→hw:3,0；ttyUSB8→ttyUSB4）→ 按名字/别名取。
- 红线：不动 PA（`pactl` 观测者效应会造 EBUSY）；测 ALSA 必取 `$?`；USB 分支掉线先查线；`crontab` 必须 `-u jetson`；`docker compose up -d` 会收敛同项目里不一致的容器。
- 注意：**宿主版语音回滚路径已不存在**（旧源码已删）→ 回滚只能走容器路径或从云端重拉。

## 未完成 / 下一步
1. ⏳ **701 nav 仓有未上云的改动**：19 个已跟踪文件被改 + 20 个未跟踪（+ 211 个删掉的 demo 地图）——属他人 WIP，本任务未动；若要留档需 commit+push（建议 `codex/*` 分支）。
2. ⏳ **`/keyframe` 三格面板顺序**：固件 `cam_topics=B,A,C` 对 715 = 左,前,右，在 701 上呈现为 前,左,右；未改（固件红线、镜像两款共用）→ 待用户决策。
3. ⏳ 仍在 701 的大件（证据不足或超范围，未删）：`docker_ws_backup` 8.1G、`backup/` 1.5G、`jetson0826-src-build` 569M、`kn_nav_backup` 165M、`container-fixes` 176M、`scout-nav-product-build` 1.4G、`voice-image-build` 341M、`*.bag` 1.1G。
4. 小缺陷：`d360_deploy/nav2d/install_2d_nav.sh` 第 1 行孤立 `205`；语音脚本自验 `crontab` 检查少 `-u`（假 PASS）。
5. 715：`core`/`ota_web` 仍 1.0.22（compose 已指 1.0.23，下次重启统一）；715 公钥已清空（交付要求）。
6. 挂起：`mttcan` 自加载（冷启动 `can0` 不存在 → 底盘激活 NONE）；4G PPP-vs-ECM 未确证（勿在交付机上试）。

## 验证状态 / 禁止
- 真机已验证项见 `facts` 的 `acceptance` / `camera_config_2026_09_18` / `cleanup_2026_09_18`；**未做**：nav 仓改动提交、`/keyframe` 顺序调整、715 复测。
- 用户快速模式：未跑仓库测试；不得把「已上传/已部署」当成「功能已验证」。
- 待用户决策：出货版是否保留免密 sudo（`jetson` 仍是弱口令）；工作台主分支 3.3GiB 大文件问题由另一 AI 处理。
