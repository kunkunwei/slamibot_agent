# 冷启动时序稳定性测试（D360 / 715、701 通用）

- 建立时间：2026-09-17
- 目的：量出「上电 → 可用」每一环的真实耗时，判定慢/失败卡在哪一环；为修竞争条件提供可重复证据。
- 探针脚本：`tmp/boot_timeline_probe.sh`（设备上运行，只用单调时钟）
- 关联：`known-issues/livox-bind-fails-before-eth0-ready-2026-09-17.md`

## 0. 为什么必须用单调时钟

这些设备**没有保电 RTC**（`tegra_rtc: setting system clock to 1970-01-01T00:00:28 UTC`）。
一次开机内墙钟会跳变 3~4 次：

| 阶段 | 墙钟来源 | 715 实测 |
|---|---|---|
| 内核早期 | 内核默认值 | `6月 18 04:29:39` |
| RTC 设定 | tegra_rtc（无电池） | `1970-01-01T00:00:28` |
| timesyncd 恢复 | `/var/lib/systemd/timesync/clock` | `2026-09-17 13:51:02`（上次关机时间，**落后 12 分**） |
| NTP 首次同步 | 网络 | `2026-09-17 14:03:41`（**前跳 12 分 39 秒**） |

后果：`dmesg -T`、`journalctl` 默认格式、`docker inspect` 的墙钟字段互相矛盾，无法直接排序。
**一律改用单调时钟**：`journalctl -b -o short-monotonic`、裸 `dmesg`（不加 `-T`）、`/proc/uptime`。

## 1. 被测依赖链（顺序即判据）

```
上电
 → 内核/系统（systemd-analyze）
 → docker 守护就绪
 → 四容器运行（core / firmware-sensors / ota_web / scout-nav）
 → eth0 拿到雷达网静态 IP（192.168.1.55）        ← 与下一环是竞争
 → livox 节点启动并绑定该 IP → 连上雷达 192.168.1.124
 → 雷达出 IMU/点云 → /livox/lidar 有数据
 → /clock 开始有数据流（唯一发布者 = livox，懒初始化于 PublishImuData）
 → timeshare 创建 → 相机出图 → /keyframe
 → nav_multi 拿到有效时钟 → 导航可用
 → 5001 状态页完整、driver_status=15、LED 正常
 → 六麦阵列自身启动完成（1f3a → 18d1 → 2208）→ 声卡可用 → run_mic → WAIT_WAKE
```

**这条链上任何一环失败，下游全部无限期停滞**（没有超时、没有重试），表现就是"卡住/很慢"。

## 2. 里程碑与通过标准

| # | 里程碑 | 检查 | 目标 |
|---|---|---|---|
| 1 | docker 守护就绪 | `docker info` | ≤30s |
| 2 | 四容器运行 | `docker ps` 命中 4 个 | ≤60s |
| 3 | eth0 有 192.168.1.55 | `grep 192.168.1.55 /proc/net/fib_trie` | 记录 |
| 4 | 雷达可 ping | `ping -c1 192.168.1.124` | 记录 |
| 5 | `/livox/lidar` 出数据 | `rostopic hz` | ≤90s |
| 6 | `/clock` 有发布者 | `rostopic info /clock` | ≤90s |
| 7 | `/clock` 有数据流 | `rostopic hz /clock` | ≤90s |
| 8 | timeshare 已创建 | 容器内 `test -e /dev/shm/timeshare` | ≤90s |
| 9 | 相机出图 | `rostopic hz /SLB_CAM_A/compressed` | ≤120s |
| 10 | `/keyframe` 出数据 | `rostopic hz /keyframe` | ≤120s |
| 11 | `driver_status=15` | `rostopic echo -n1` | ≤120s |
| 12 | 5001 页面 200 | `curl` | ≤120s |
| 13 | 六麦 USB 枚举 | `lsusb \| grep 2208:0001` | 记录（可能数分钟） |
| 14 | `/dev/lg_speech_serial` | `ls -l` | 记录 |
| 15 | 六麦声卡可用 | `arecord -l \| grep ListenGo` | 记录 |
| 16 | `run_mic` 运行 | `pgrep` | 记录 |
| 17 | 语音 `WAIT_WAKE` | `tail sherpa.log` | 记录 |

## 3. 测试步骤

1. 把探针放到设备（**不要用 scp 传业务源码**；此脚本是测试工具，可放 `/home/jetson/`）：
   `bash boot_timeline_probe.sh` 需可执行、LF 换行。
2. 每次冷启动：
   - 断电 ≥30 秒（让 BOX 内六麦模块也彻底断电，它的启动是独立变量）
   - 上电后立即拉起探针：
     `nohup bash /home/jetson/boot_timeline_probe.sh >/dev/null 2>&1 &`
     （或写进 crontab `@reboot`，但要接受探针本身也受开机时序影响）
   - 等探针跑完（默认最长 30 分钟）或到全部里程碑达成
3. 采集同一次开机的原始证据（便于事后复核）：
   ```bash
   sudo journalctl -b -o short-monotonic > /tmp/boot-$N-journal.log
   sudo dmesg                            > /tmp/boot-$N-dmesg.log      # 不要 -T
   systemd-analyze blame                 > /tmp/boot-$N-blame.log
   docker inspect core firmware-sensors ota_web scout-nav \
     --format '{{.Name}} {{.State.StartedAt}} {{.RestartCount}}' > /tmp/boot-$N-containers.log
   lsusb > /tmp/boot-$N-lsusb.log
   ```
4. **建议次数：连续 10 次冷启动**。样本太少无法区分"偶发"与"必现"。
5. 701 与 715 用同一协议各跑一遍，用于分离「设备个体问题」与「系统性竞争」。

## 4. 结果判读

| 现象 | 指向 |
|---|---|
| 里程碑 3 晚于 5 | eth0 静态 IP 竞态 → livox bind 失败（本次已确认） |
| 里程碑 5/6/7 失败且 8 之后全失败 | 雷达链路断，`/clock` 缺失 → 下游全停（**最严重**） |
| 里程碑 13 长时间 FAIL | 六麦模块自身启动慢/卡（看 `dmesg \| grep 1-2.4.4.3` 的三段式枚举） |
| 里程碑 1/2 之间 >20s | 容器启动延迟（本次实测 715 41.7s、701 53.3s，机理待定） |
| 里程碑 11 恒为 8/11 而非 15 | 某个驱动位缺失，对照 `driver_status` 位定义 |

## 5. 已知会在测试中复现的问题

- **livox 初始化失败不退出**：SDK 初始化失败只打日志、继续 `while(ros::ok())` 空转，`respawn` 永远不触发（详见 known-issues）。
- **六麦阵列三段式启动**：`1f3a:efe8` → `18d1:d002 (Tina ADB)` → `2208:0001`；本次冷启动到 1098s 才可用，期间 Jetson 侧枚举报 `-110`/`-71`。
- **时钟跳变**：任何用墙钟做超时/排序的逻辑都可能被 12 分钟的前跳影响。
