# 交接：2026-08-26 生产 hotfix — /scan 断链 + 3D 箭头 + 膨胀 0.10

> 给下一会话的交接文档。本会话结束于「代码已同步、容器已重启、待用户重启导航栈验证」。
> 用户计划重新开启会话继续测试。

## 一句话状态
**三件事已改好代码/参数，都卡在同一个待验证点：重启导航栈让 robot_state_publisher 存活。**

| 项 | 状态 | 生效条件 |
|---|---|---|
| ① 膨胀 0.10/12（三处一致） | 代码+参数已同步 | 重启 move_base |
| ② /robot_map_pose 转发（3D 箭头） | 代码已部署+容器已重启 | `/amcl_pose` 有消息 |
| ③ /scan 断链（导航根因） | 根因已定位 | robot_state_publisher 存活 |

- ②和③是同一根因链：`/scan` 断 → AMCL 无定位 → `/amcl_pose` 空 → 转发不触发。
- **修好 ③，②自动出现发布者。**

## 机器人 & 环境
- Jetson Orin NX，`192.168.31.135`（公司 Wi-Fi），用户 `jetson`，SSH 用 `C:\Users\kun\.ssh\id_rsa`，必须 `-F /dev/null -o IdentitiesOnly=yes`。
- ROS1 Noetic，master `127.0.0.1:11311`，/use_sim_time=true，虚拟时钟 `/clock` 由 livox 发布。
- 导航栈 roslaunch 跑在**宿主机**（launch_manager 管理），容器 `scout-nav` 内跑 rosbridge:19090 + nav_multi_node + uvicorn:5000 + nginx。
- 容器入口 `/usr/local/bin/nav-api-entrypoint`（bash，`wait $API_PID` 结尾）→ **kill uvicorn 会使容器退出，只能 `docker restart scout-nav`**。

## 本会话已完成的修改

### ① 膨胀 0.10（任务 13）
- 本地 `F:\d360_nav2D\src\my_nav\config\tuned2\` 三文件：
  - `costmap_common_params_tuned.yaml`：inflation_radius 0.06→**0.10**
  - `global_costmap_params_tuned.yaml`：0.33→**0.10**、cost_scaling_factor 1→**12**（原全局/局部不一致，违反文件注释"必须严格一致"）
  - `local_costmap_params_tuned.yaml`：0.05→**0.10**
- 三处现统一 **0.10 + 12.0**（footprint 0.306×0.29）。
- 板上 src/install/share 及参数服务器已同步（带 `inflation_layer/` 前缀路径）。**生效需重启 move_base。**

### ② /robot_map_pose 转发（3D 箭头）
- 本地 `F:\d360_nav2D\src\nav_api\fastapi_service\ros_client.py` +27 行（`_robot_map_pose_pub` + `_publish_robot_map_pose`，`_on_pose` 里转发 /amcl_pose→/robot_map_pose PoseStamped frame_id=map）。`git diff` 确认只此 27 行。
- **只同步 27 行**到板上 src+install 两份（不含本地多出的 `get_scout_detection_snapshot` 7 行，板上 base_mode 不调用）。
- 补丁脚本留档：`.ai-workspace/tmp/capture-hotfix-20260826/board_rosclient/patch_robot_map_pose.py`。
- **容器已 `docker restart scout-nav`**，uvicorn PID 175 运行中，`py_compile` 通过，`grep -c robot_map_pose`=11。

## 下一会话待做（用户已同意重启导航栈）

### 第 1 步：请用户重启导航栈（my_nav_launch.launch，launch_manager 管理）
重启会让 robot_state_publisher 重新拉起 → laser→base_link TF → /scan → AMCL → /amcl_pose → /robot_map_pose 全部恢复，膨胀 0.10 也生效。

### 第 2 步：验证（板上宿主机跑）
```bash
source /opt/ros/noetic/setup.bash
rostopic hz /scan                # 期望有频率
rostopic hz /amcl_pose           # 期望有消息
rostopic info /robot_map_pose    # 期望 Publishers 非空
rostopic echo /robot_map_pose -n 1
tf_echo base_link laser          # 期望 static TF
# 膨胀确认（带前缀！）
rosparam get /move_base/global_costmap/inflation_layer/inflation_radius   # 期望 0.1
rosparam get /move_base/local_costmap/inflation_layer/inflation_radius    # 期望 0.1
```

### 第 3 步：验证 3D 箭头
APP 操作 ⊹/◎ 后看箭头是否更新（需用户真机确认）。

## 风险与边界
- **若重启后 RSP 又"0.3s finished cleanly"秒退**：需改 launch 顺序（RSP 在 URDF 参数后启动）。**属业务代码修改，先跟用户确认再动。** 证据：参数服务器 /robot_description 完整（laser_joint fixed base_link→laser），说明模型没问题，纯粹是 RSP 没跑。
- 小车必须保持静止：不主动发 /cmd_vel，make_plan 测试只规划不动车。
- 用户敏感点：不擅自杀进程、不删数据、不 `git reset --hard`、APP 编译安装由用户手动做。
- 板上 ros_client.py 若需回滚：`git checkout -- <file>`（src 在 git 仓库）或重新 catkin build 覆盖 install。

## 关键文件
- 板上 roslaunch 入口：`/home/jetson/Scout_mini_navigation/src/my_nav/launch/my_nav_launch.launch` → `lidar_to_scan.launch` → `scout_mini_robot_base.launch:59`（robot_state_publisher）
- 板上后端：`/home/jetson/Scout_mini_navigation/{src,nav_api/...}` 与 `install/lib/python3/dist-packages/fastapi_service/ros_client.py`
- 本地镜像：`F:\d360_nav2D\src\{my_nav, nav_api}\...`

## 关联文档
- `known-issues/robot-state-publisher-exits-scan-broken-2026-08-26.md`
- `known-issues/robot-map-pose-no-publisher-2026-08-26.md`
- 任务条目：`tasks/current.md` → `TASK-2026-08-26-001`
