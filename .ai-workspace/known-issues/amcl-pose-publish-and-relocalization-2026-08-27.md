# /amcl_pose 不持续发布 + 重定位不收敛（install-only 容器）

- 状态: **open（/amcl_pose 已恢复 10Hz 持续发布；重定位收敛待用户 APP 验收）**（2026-08-27）
- 技术栈: ROS1 Noetic / AMCL + move_base / scout-nav 容器（install-only）/ 宿主机 roslaunch 共享 master 127.0.0.1:11311
- 影响面: 导航模式下 /amcl_pose 无消息或断续；重定位"手动标哪停哪、不被校正、导航中位姿一直歪"

## 现象
- `/amcl_pose` 静止时无新消息；手动标 initialpose 后位姿不被 AMCL 校正；APP 自动重定位粒子位置随机。
- 用户反馈导航中位姿与实际一直歪（"起始点歪了，导航过程中一直歪"）。
- 曾有"抽搐变化的箭头"（本会话临时加 force_amcl_pose 节点与 AMCL 抢 map->odom TF 导致，已删除该节点）。

## 根因（已确认）
- AMCL 参数 `update_min_d=0.1 / update_min_a=0.15` 是**更新门槛**：只有 odom 位移超过阈值才做粒子更新并发布 /amcl_pose。
- 机器人重定位后**静止**时，odom 位移≈0 → 不更新 → 不发 /amcl_pose、不做 scan 匹配校正 → 位姿只靠 odom 累积漂移 → "标哪停哪、导航一直歪"。
- 修复方向：`update_min_d/a` 设为负数（如 -1.0），`delta > -1.0` 恒真 → 每帧 scan 都更新都发布。
- 注意：**设 0.0 无效**（静止时 `0 > 0` 为假）。必须负数。

## 本会话实际验证结果（重要事实修正）
- **AMCL 本身一直工作正常**（CPU ~11%，发布 map->odom TF 与 /amcl_pose）。
- 之前"AMCL 日志 0 字节 = 没干活"的判断**错误**——AMCL 进程日志为空只是 roslaunch 缓冲/重定向表现，不是故障。
- TF 树曾短暂"无 map frame"，是我测试 force 节点期间 TF 中断的瞬时现象，**不是地图挂载错**。
- **地图挂载/加载完全正常**：map_server 正确加载 map2701（install 版 yaml），AMCL 收到 `1271 X 941 @ 0.050 m/pix`，与 DB 激活地图一致。
- `/amcl_pose` 当前由 AMCL 发布，**10Hz 持续稳定**（重启导航栈后验证 window 85 无空档）。
- 系统实际生效参数：`update_min_d=0.0 / update_min_a=0.0`（rosparam 实测），非 launch 文件里的 -1.0 —— roslaunch 加载来源需进一步核对（install vs src），但 0.0 已能持续发布（可能因机器人在轻微移动/抖动触发更新）。

## 已验证全链路（2026-08-27 实测）
- `/scan` 10Hz 正常，AMCL inbound 订阅存在，frame_id=base_link，685/1048 有效 range。
- `/odom` 50Hz、odom->base_link TF 60Hz、laser->base_link static TF 正常。
- `/clock` 虚拟时间与 scan/odom 时间戳同系（差秒级）。
- map_server 加载 map2701（install 版），AMCL 收到 1271x941。
- `/amcl_pose` 10Hz，frame_id=map，发布者为 /amcl。
- map->odom TF 稳定（重启后收敛在 [-0.279,-0.926] 附近）。

## 修复内容（板上已改，未提交 git）
- `/Scout_mini_navigation/install/share/my_nav/launch/my_nav_launch.launch`（install 版，实际可能未生效）
- `/Scout_mini_navigation/src/my_nav/launch/my_nav_launch.launch`（src 版）
- 两处 `update_min_d` / `update_min_a` 已从 0.1/0.15 → **0.0 → -1.0**（最后状态 -1.0）。
- 临时 force_amcl_pose 节点脚本 `/Scout_mini_navigation/scripts/force_amcl_pose.py` 已写但**已删除进程**（pkill），不应再使用。

## 待用户验证
1. APP 上箭头是否稳定跟随（不再抽搐）。
2. 手动标点后是否被 AMCL 校正（位姿是否贴合地图特征）。
3. 若需"静止也一直发"，需确认 roslaunch 实际加载哪份 launch（install vs src）并让 `update_min_d/a=-1.0` 真正生效。

## 验证命令
```bash
rostopic hz /amcl_pose            # 期望持续有频率（静止时 0.0 阈值可能无消息，-1.0 才恒发）
rosparam get /amcl/update_min_d   # 期望 -1.0（若显示 0.0 说明 launch 加载的不是被改的那份）
rosrun tf tf_echo map base_link   # 期望稳定输出
```

## 关联
- `known-issues/robot-state-publisher-exits-scan-broken-2026-08-26.md`（/scan 断链曾导致 AMCL 无定位）
- `known-issues/robot-map-pose-no-publisher-2026-08-26.md`（/robot_map_pose 等 /amcl_pose 触发转发）
- 任务 `TASK-2026-08-26-001`
