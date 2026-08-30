# FAST_LIO 高精度里程计接入 2D 导航（TF 树重构 + AMCL 换 odom frame）

- 状态: **resolved（No point + bad_alloc 崩溃已修复并验证通过）**（2026-08-27）
- 技术栈: ROS1 Noetic / FAST_LIO_gravity_align（板上已编译 install 版）/ AMCL + move_base / scout-nav 容器
- 影响面: 用 FAST_LIO 激光惯性里程计替代底盘轮式 odom 作为 AMCL 输入，解决"重定位不准、导航位姿一直歪"

## 核心阻塞（2026-08-27 已定位根因，待重启验证）
- `laserMapping`（fastlio_gravity_align_mapping 节点）启动后持续输出 `No point, skip this scan!`，随后 **`std::bad_alloc` 内存耗尽被 SIGKILL（exit code -9）**，roslaunch 整体退出，launch_manager 反复重启。
- 不发布 `/cloud_registered` 点云、不发 `camera_init→body` TF、无 `/Odometry`。
- 后果：TF 链 map→camera_init→body→base_link→laser 断在 camera_init，AMCL 拿不到高精度里程计，3D 定位/重定位不工作。

### 根因（已确认，2026-08-27 实测）
- **lidar 数据完全正常**：容器内探测 `/livox/lidar` = CustomMsg，**每帧 20064 点**，frame_id=livox_frame，坐标有效（非零点充足）。**不是 livox 驱动问题。**
- **运行配置 `time_sync_en: true`（容器 install 版 mid360.yaml）**，gitee 原版为 `false`。
  - `time_sync_en=true` 触发 laserMapping.cpp:319 的一次性自同步：`timediff_lidar_wrt_imu = last_timestamp_lidar + 0.1 - last_timestamp_imu`，并把所有 IMU 时间戳重映射（laserMapping.cpp:343-347）。
  - 自同步偏移不准 → IMU/lidar 时间对齐失败 → `sync_packages` 配帧失败 → `feats_undistort` 空 → "No point" → 扫描帧在 buffer 积压不消耗 → 内存持续增长 → `std::bad_alloc` → 进程被杀。
- 根因证据链：laserMapping 已订阅 `/livox/lidar`（rosnode info 确认）→ 但 `/cloud_registered`/`/Odometry` 均 "no new messages" → /tmp/fastlio_run.log 显示 `No point` → `std::bad_alloc` → exit -9。
- **已做的修改**（容器内，2026-08-27）：
  - `/Scout_mini_navigation/install/share/fast_lio_gravity_align/config/mid360.yaml`：`time_sync_en: true → false`（已备份 `/tmp/mid360.yaml.bak-timesync-20260827`）。
  - 规范仓库 `F:\d360_nav2D\src\FAST_LIO_gravity_align\config\mid360.yaml` 本来就是 `false`，与 gitee 一致，无需改动。
  - mapping_mid360.launch 通过 `$(find fast_lio_gravity_align)/config/mid360.yaml` 加载，rospack find → install 路径 → 已修的这份就是运行时文件。
### 修复验证（2026-08-27，已通过）
- 通过后端 API（端口 5000）`switch_to_mapping` 干净重启 FAST_LIO（launch_manager.py 的 start_mapping 启动 fastlio_mapping.launch），新配置生效后实测：
  - ✅ `laserMapping` 进程稳定运行（不再 bad_alloc 崩溃）
  - ✅ rosparam `/common/time_sync_en = false`、`/preprocess/lidar_type = 1`
  - ✅ `/cloud_registered` 9.999 Hz（publisher=/laserMapping）
  - ✅ `/Odometry` 10.000 Hz，frame=camera_init → child=body
  - ✅ `/scan` 9.998 Hz，frame=base_link，360°，range 0.1–40m
  - ✅ `camera_init→body` TF 有效（Translation [0.013,0.012,-0.002]）
- 操作记录：先 `docker exec scout-nav kill` 清掉卡死的 fastlio roslaunch（注意**容器/宿主 PID 命名空间不同**，容器内要 kill 容器视图的 PID），再经 API 停→启导航，最后 `GET /api/control/mode/mapping` 切建图模式拉起 FAST_LIO。
- **发现的架构事实**：launch_manager.py 中 `start_mapping()` 启动 fastlio_mapping.launch（FAST_LIO 在建图模式运行）；`start_navigation()` 只启动 my_nav_launch.launch（AMCL+move_base），**不含 fastlio**。known-issue 里"AMCL 换 camera_init odom"的改动当前无运行时支撑——导航模式没跑 FAST_LIO。

## 下一步（3D 重定位目标）
1. 把 gitee `FAST_LIO_LOCALIZATION` 补全进容器 install（launch/config/scripts/lib；CMake 无 install 规则 → 需手动补；scripts 是 python2 → 需适配 python3；open3d 0.9→0.16 API）。
2. 接入导航链：参考 gitee `fastlio_localization_with_2d_nav.launch`，用 transform_fusion 提供的 map→odom 替代/增强 AMCL。

## 已确认排除（不是差异，不要在这些上面浪费时间）
1. **FAST_LIO C++ 源码与 gitee 完全一致（md5 相同）**：
   - `laserMapping.cpp` = `2b75b9d06000b41ca0572b3fe610b688`（板上 src 与 gitee F:\slamibot_test 相同）
   - `preprocess.cpp` = `18dd377aff549ba7626df21f11a0d941`（相同）
   - src 文件清单一致：IMU_Processing.hpp / laserMapping.cpp / preprocess.cpp / preprocess.h
2. **FAST_LIO 配置原始一致**：gitee `config/mid360.yaml` 为 `time_sync_en: false`、`time_offset_lidar_to_imu: 0.0`。
3. **FAST_LIO launch 一致**：板上 `install/share/my_nav/mapping_launch/fastlio_mapping.launch` 只是 include `$(find fast_lio_gravity_align)/launch/mapping_mid360.launch` + 一个 `/cloud_registered→/global_cloud_navigation` relay。
4. **livox 消息类型一致**：`/livox/lidar` = `livox_ros_driver2/CustomMsg`，`/livox/imu` = `sensor_msgs/Imu`。
5. **livox publish_freq = 10.0**（与 gitee mid360.launch 一致）。
6. **温度/硬件**：设备从未换过，温度正常（用户多次明确），不是硬件问题。

## 根因方向（待确认，用户指向"代码问题"）
- **livox 驱动版本差异**。板上 livox 驱动跑在 **`/root/SLAMIBOT_D360_Framework/install/lib/livox_ros_driver2`**（另一套 framework，非 Scout_mini_navigation），启动命令是直接 node：
  ```
  livox_ros_driver2_node 100000000000000 __name:=livox_lidar_publisher2
  ```
  无 launch、无 xfer_format/publish_freq 等参数。
- gitee 通过 `livox_ros_driver2/launch_ROS1/mid360.launch` 启动（xfer_format=0, publish_freq=10.0, data_src=0, multi_topic=0, output_type=0）。
- 疑似两套 livox 驱动源码版本不同，点云/IMU 时间戳处理逻辑（`GetEthPacketTimestamp`）不同，导致 lidar 时间戳滞后 imu ~1.5s，FAST_LIO 的 `sync_packages`/undistortion 配帧失败 → feats_undistort 为空 → "No point"。
- 注：时间戳差是现象不是根因；根因是**哪套 livox 驱动、哪份时间戳代码**在跑。

## 用户明确指示（必须遵守）
1. **不要再搞时间差测量**（用户认为钻牛角尖浪费时间）。
2. **直接抄 gitee**（F:\slamibot_test\d360_nav2D，一定能跑）。
3. 设备没换、温度正常，**只有代码问题**。
4. **一定要改干净，不要再依赖 src**（install-only）；前同事"直接挂载 src"省事但工程不规范、依赖混乱。
5. 不要浪费时间看日志，限时快速行动。

## 下一步（重开会话后执行）
1. 对比两套 livox 驱动源码：gitee `F:\slamibot_test\d360_nav2D\src\livox_ros_driver2` vs 板上 `/root/SLAMIBOT_D360_Framework`（含 install 产物与可能的 src）。
2. 把 gitee 的 livox 驱动（源码 + `mid360.launch` + `MID360_config.json`）作为唯一基线，替换/重建板上 livox 驱动，使其与 gitee 完全一致。
3. 恢复 FAST_LIO `mid360.yaml` 为 gitee 原始值（`time_sync_en: false`、`time_offset_lidar_to_imu: 0.0`），撤销本会话对 time_sync/time_offset 的改动。
4. 重启验证 TF 链 map→camera_init→body→base_link→laser 连通、`/cloud_registered` 有输出、`/scan` 有效点 >5m。

## 已完成的改动（本会话，板上 install 版 + 宿主机 src 版）
| 文件 | 改动 |
|---|---|
| `my_nav_launch.launch` | AMCL `odom_frame_id` odom→camera_init |
| `lidar_to_scan.launch` | `cloud_in` /livox_pcl0→/cloud_registered；`max_height` 0.5→1.0；新增 body→base_link static TF |
| `local_costmap_params_tuned.yaml` | global_frame odom→camera_init |
| `base_mode.py` | pub_tf:=true→false |

## 关联
- `known-issues/amcl-pose-publish-and-relocalization-2026-08-27.md`
- `known-issues/robot-state-publisher-exits-scan-broken-2026-08-26.md`
