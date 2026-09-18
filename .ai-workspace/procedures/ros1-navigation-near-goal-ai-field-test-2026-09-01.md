# ROS1 2D 导航“近目标绕行且无法停止”AI 现场测试交接文档

- 文档日期：2026-09-01 CST
- 适用机器人：SLAMIBot D360 / Scout Mini / Jetson Orin NX
- 当前技术基线：Ubuntu 20.04 + ROS1 Noetic
- 测试性质：**只读诊断，不修改、不部署、不重启**
- 当前演示容器：`scout-nav-timefix-20260827`
- 当前演示镜像：`scout-nav:jetson0826-src-timefix-20260827`

## 1. 给执行 AI 的完整提示词

将下面整段提示词交给负责现场测试的 AI：

> 你正在诊断一台 Jetson Orin NX 上的 ROS1 Noetic 2D 导航系统。现象是：在 RViz 发送约 0.5–1 m、空旷直线路径目标后，小车接近目标仍不断规划，GlobalPlanner 或 TEB 出现绕来绕去的轨迹，move_base 不能稳定进入 SUCCEEDED。
>
> 本轮只允许 READ_ONLY。禁止修改源码、ROS 参数、数据库、地图、Compose、Docker 镜像和容器；禁止 docker restart/stop/rm/compose up、kill、pkill、rosnode kill、rosparam set/delete、git checkout/reset/clean、文件覆盖和部署。禁止启动第二个 Scout 驱动或第二套导航。当前演示容器 `scout-nav-timefix-20260827` 和镜像 `scout-nav:jetson0826-src-timefix-20260827` 必须原样保留。
>
> 按本文阶段顺序执行。所有命令必须有限时或有限条数，不能留下持续运行的 rostopic、tf_echo、rosbag 或后台进程。先验证容器、节点、Topic publisher、TF publisher、运行参数和 src/install 实际来源，再进行一次人工配合的 0.5–1 m 短目标测试。
>
> 最终必须判断属于以下哪一类：A. GlobalPlanner 已绕；B. GlobalPlanner 直但 TEB 绕；C. 两条路径都直但底盘/位姿不收敛；D. 到点附近 TF/odom 跳变；E. 证据不足。不得凭参数注释直接断言根因。
>
> 输出必须包含：执行时间、容器/镜像、节点列表摘要、每个关键 Topic 的 publisher、TF 链及 broadcaster、运行 rosparam、src/install 来源、短目标时间线、GlobalPlanner/TEB/cmd_vel/odom/status 的对应关系、根因排序、关键原始输出和下一步最小 A/B 建议。任何修复都必须等用户另行授权。

## 2. 已知事实，禁止重新猜测

### 2.1 本地源码对比结论

老仓库：

```text
F:\slamibot_test\d360_nav2D
branch: master
HEAD: a16dc8f18cd93a0f2cd2628dce226821ea457efe
```

当前产品开发仓库：

```text
F:\d360_nav2D
branch: codex/product-nav-runtime-refactor-20260831
HEAD: ec245a7eab7c06ab68c2679b13875d03a33fcc69
```

两仓库的以下导航核心内容相同：

- `src/my_nav/launch/my_nav_launch.launch`
- `src/my_nav/launch/move_base_tuned2.launch`
- `src/my_nav/config/tuned2/teb_local_planner_params_tuned.yaml`
- `src/my_nav/config/tuned2/dwa_local_planner_params.yaml`
- `src/my_nav/launch/fastlio_localization_with_2d_nav.launch`
- 整个 `src/scout_ros/scout_base`

因此，不允许直接用 `F:\slamibot_test` 整目录覆盖当前代码。老仓库本身已经包含可疑的 Go2/窄通道专项参数。

### 2.2 已知可疑参数

AMCL：

```xml
odom_model_type="omni-corrected"
update_min_d="0.1"
update_min_a="0.15"
recovery_alpha_slow="0.001"
recovery_alpha_fast="0.1"
```

Scout 管理器却明确使用：

```text
is_scout_omni:=false
```

TEB：

```yaml
xy_goal_tolerance: 0.12
yaw_goal_tolerance: 0.15
complete_global_plan: True
global_plan_overwrite_orientation: True
allow_init_with_backwards_motion: True
weight_kinematics_nh: 1000
weight_kinematics_forward_drive: 80
min_obstacle_dist: 0.1
inflation_dist: 0.25
```

footprint：

```yaml
[[0.306, 0.29], [0.306, -0.29], [-0.306, -0.29], [-0.306, 0.29]]
```

尺寸约为 `0.612 m × 0.58 m`，需要后续与真实 Scout Mini 外形和 `base_link` 原点核对。

### 2.3 后期结构变化

1. Scout 驱动启动所有权从导航 launch 转移到 FastAPI `base_mode.py`。
2. `base_mode.py` 默认从 install 路径加载 Scout launch：

```text
/Scout_mini_navigation/install/share/scout_base/launch/scout_mini_base.launch
```

3. costmap 膨胀由老版：

```text
common=0.06
global=0.33 / cost_scaling_factor=1
local=0.05
```

统一成当前：

```text
common/global/local=0.10
cost_scaling_factor=12
```

4. 新增 3D 重定位，可能广播：

```text
map → camera_init
```

标准 2D AMCL 则维护：

```text
map → odom → base_link
```

## 3. 安全边界

### 3.1 本轮允许

- `docker ps`、`docker inspect`、`docker stats --no-stream`
- `docker exec` 内执行只读 ROS 查询
- `rosnode list/info`
- `rostopic list/info/type/hz`，但必须有限时
- `rostopic echo -n N`
- `rosparam get/list`
- `tf_echo`、`tf_monitor`，但必须使用 `timeout`
- `ps`、`pgrep`、`readlink`、`sha256sum`、`find`、`ls`
- 人工通过 RViz 发送一次短距离目标

### 3.2 本轮禁止

```text
docker restart/stop/start/rm
Docker Compose up/down/recreate
kill/pkill/rosnode kill
rosparam set/delete/load
发布 /cmd_vel 或伪造传感器消息
git checkout/reset/clean/pull
修改或覆盖 src/install
构建、部署、替换镜像
删除日志、地图、PCD、DB
启动 rosbag 长时间录制
启动第二个 AMCL、move_base、Scout 驱动或 3D 重定位
```

如果任一检查需要写文件、重启或改参数，停止并向用户申请单独授权。

## 4. 连接方式

优先 LAN：

```powershell
ssh -F NUL -i "C:\Users\kun\.ssh\id_rsa" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 jetson@192.168.31.135
```

若连接超时，只报告：

```text
JETSON_UNREACHABLE
时间：<绝对时间>
入口：192.168.31.135:22
```

不得因为 LAN 超时就修改网络配置或尝试危险恢复操作。

以下命令默认在 Jetson 宿主机执行。容器变量：

```bash
NAV_CONTAINER=scout-nav-timefix-20260827
```

## 5. 阶段 0：确认测试对象没有漂移

执行：

```bash
date -Is
hostname
uptime

docker ps --no-trunc --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
docker inspect scout-nav-timefix-20260827 \
  --format 'name={{.Name}} image={{.Config.Image}} id={{.Image}} started={{.State.StartedAt}} restart={{.RestartCount}} status={{.State.Status}}'
docker inspect scout-nav-timefix-20260827 \
  --format '{{range .Mounts}}{{println .Source " -> " .Destination " rw=" .RW}}{{end}}'
docker stats --no-stream scout-nav-timefix-20260827
```

通过条件：

- 容器名称是 `scout-nav-timefix-20260827`；
- 镜像是 `scout-nav:jetson0826-src-timefix-20260827`；
- 容器处于 running；
- `RestartCount` 没有在测试中增长。

若名称或镜像不一致，停止测试并报告实际值，不要自行切换。

## 6. 阶段 1：确认实际加载的是 src、devel 还是 install

执行：

```bash
docker exec scout-nav-timefix-20260827 bash -lc '
set -u
printf "ROS_PACKAGE_PATH=%s\n" "${ROS_PACKAGE_PATH:-}"
printf "CMAKE_PREFIX_PATH=%s\n" "${CMAKE_PREFIX_PATH:-}"
command -v rospack
rospack find my_nav || true
rospack find scout_base || true
printf "--- my_nav runtime files ---\n"
find /Scout_mini_navigation/install/share/my_nav -maxdepth 3 -type f 2>/dev/null | sort | head -100
printf "--- source files ---\n"
find /Scout_mini_navigation/src/my_nav/launch /Scout_mini_navigation/src/my_nav/config/tuned2 -maxdepth 2 -type f 2>/dev/null | sort
'
```

计算关键源码/install 文件指纹：

```bash
docker exec scout-nav-timefix-20260827 bash -lc '
for f in \
 /Scout_mini_navigation/src/my_nav/launch/my_nav_launch.launch \
 /Scout_mini_navigation/src/my_nav/launch/move_base_tuned2.launch \
 /Scout_mini_navigation/src/my_nav/config/tuned2/teb_local_planner_params_tuned.yaml \
 /Scout_mini_navigation/src/my_nav/config/tuned2/costmap_common_params_tuned.yaml \
 /Scout_mini_navigation/src/my_nav/config/tuned2/global_costmap_params_tuned.yaml \
 /Scout_mini_navigation/src/my_nav/config/tuned2/local_costmap_params_tuned.yaml \
 /Scout_mini_navigation/install/share/my_nav/launch/my_nav_launch.launch \
 /Scout_mini_navigation/install/share/my_nav/launch/move_base_tuned2.launch \
 /Scout_mini_navigation/install/share/my_nav/config/tuned2/teb_local_planner_params_tuned.yaml \
 /Scout_mini_navigation/install/share/my_nav/config/tuned2/costmap_common_params_tuned.yaml \
 /Scout_mini_navigation/install/share/my_nav/config/tuned2/global_costmap_params_tuned.yaml \
 /Scout_mini_navigation/install/share/my_nav/config/tuned2/local_costmap_params_tuned.yaml; do
  if [ -f "$f" ]; then sha256sum "$f"; else echo "MISSING $f"; fi
done
'
```

必须记录：

- `rospack find my_nav` 实际指向哪里；
- install 是否缺少 `my_nav/launch` 或 `my_nav/config`；
- src 与 install 的同名文件是否一致；
- 不允许因为发现不一致就复制文件。

## 7. 阶段 2：节点和进程唯一性

执行：

```bash
docker exec scout-nav-timefix-20260827 bash -lc '
printf "--- ROS nodes ---\n"
rosnode list | sort
printf "--- relevant processes ---\n"
ps -eo pid,ppid,lstart,args | grep -E "scout_base|move_base|amcl|transform_fusion|global_localization|FAST_LIO|fastlio|pointcloud_to_laserscan|base_mode" | grep -v grep || true
'
```

重点统计：

- `scout_base_node` 是否恰好一个；
- `move_base` 是否恰好一个；
- `amcl` 是否恰好一个；
- 是否存在 `transform_fusion.py`；
- 是否存在 `global_localization.py`；
- 是否存在额外 FAST-LIO 定位/融合进程；
- 是否能看到 FastAPI `base_mode` 启动出的 Scout 子进程。

发现重复节点时先取证，不要 kill。

## 8. 阶段 3：关键 Topic publisher 唯一性

执行：

```bash
docker exec scout-nav-timefix-20260827 bash -lc '
for t in \
 /odom \
 /cmd_vel \
 /amcl_pose \
 /initialpose \
 /tf \
 /tf_static \
 /move_base/status \
 /move_base/GlobalPlanner/plan \
 /move_base/TebLocalPlannerROS/local_plan; do
  echo "===== $t ====="
  rostopic info "$t" 2>&1 || true
done
'
```

对 `/odom`、`/tf`、`/cmd_vel` 中出现的 publisher，逐一执行：

```bash
docker exec scout-nav-timefix-20260827 bash -lc 'rosnode info /实际节点名'
```

判定：

- `/odom` 应只有一个 publisher；
- `/cmd_vel` 在导航中通常应由 move_base 控制链输出；若存在 mux，需要记录 mux 上下游，不能简单判为重复；
- `/tf` 有多个 publisher 是正常的，但 `odom→base_link` 只能有一个有效 broadcaster；
- `/initialpose` 可能有多个潜在 publisher，但需确认 3D 重定位是否正在订阅并参与运行。

## 9. 阶段 4：读取实际运行参数

执行：

```bash
docker exec scout-nav-timefix-20260827 bash -lc '
for p in \
 /amcl/global_frame_id \
 /amcl/odom_frame_id \
 /amcl/base_frame_id \
 /amcl/odom_model_type \
 /amcl/update_min_d \
 /amcl/update_min_a \
 /amcl/recovery_alpha_slow \
 /amcl/recovery_alpha_fast \
 /move_base/base_global_planner \
 /move_base/base_local_planner \
 /move_base/controller_frequency \
 /move_base/planner_frequency \
 /move_base/TebLocalPlannerROS/odom_topic \
 /move_base/TebLocalPlannerROS/map_frame \
 /move_base/TebLocalPlannerROS/xy_goal_tolerance \
 /move_base/TebLocalPlannerROS/yaw_goal_tolerance \
 /move_base/TebLocalPlannerROS/complete_global_plan \
 /move_base/TebLocalPlannerROS/global_plan_overwrite_orientation \
 /move_base/TebLocalPlannerROS/weight_kinematics_nh \
 /move_base/TebLocalPlannerROS/weight_kinematics_forward_drive \
 /move_base/global_costmap/global_frame \
 /move_base/global_costmap/robot_base_frame \
 /move_base/global_costmap/inflation_radius \
 /move_base/global_costmap/cost_scaling_factor \
 /move_base/local_costmap/global_frame \
 /move_base/local_costmap/robot_base_frame \
 /move_base/local_costmap/inflation_radius \
 /move_base/local_costmap/cost_scaling_factor; do
  printf "%s=" "$p"
  rosparam get "$p" 2>&1 || true
done
printf "--- global footprint ---\n"
rosparam get /move_base/global_costmap/footprint 2>&1 || true
printf "--- local footprint ---\n"
rosparam get /move_base/local_costmap/footprint 2>&1 || true
'
```

必须比较“运行值”和“源码值”。如果不一致，标记：

```text
RUNTIME_SOURCE_MISMATCH
```

但不执行 `rosparam set`。

## 10. 阶段 5：静止状态 TF/odom 稳定性

确保机器人静止、周围无人移动，然后执行有限时检查：

```bash
docker exec scout-nav-timefix-20260827 bash -lc 'timeout 12s rosrun tf tf_echo map odom' || true
docker exec scout-nav-timefix-20260827 bash -lc 'timeout 12s rosrun tf tf_echo odom base_link' || true
docker exec scout-nav-timefix-20260827 bash -lc 'timeout 12s rosrun tf tf_echo map base_link' || true
docker exec scout-nav-timefix-20260827 bash -lc 'timeout 12s rosrun tf tf_monitor odom base_link' || true
```

同时取有限条消息：

```bash
docker exec scout-nav-timefix-20260827 bash -lc 'rostopic echo -n 10 /odom'
docker exec scout-nav-timefix-20260827 bash -lc 'rostopic echo -n 10 /amcl_pose'
```

观察点：

- 机器人静止时，`odom→base_link` 不应持续明显位移或旋转；
- `map→odom` 可以有轻微 AMCL 修正，但不应反复大跳；
- 时间戳不应回退；
- pose 不应突然归零；
- covariance 是否异常增大；
- 同一次静止采集中，如果平移累计变化超过约 0.03 m 或 yaw 变化超过约 2°，标记为可疑，不要立即认定硬阈值故障。

## 11. 阶段 6：人工短目标复现

### 11.1 场地要求

- 使用已加载的干净地图；
- 目标方向前方 0.5–1 m；
- 路径附近无人员、桌椅、线缆和动态障碍；
- 机器人初始朝向尽量与目标方向一致；
- 现场人员随时准备急停；
- 不通过脚本发布 `/cmd_vel`。

### 11.2 测试前记录

```bash
docker inspect scout-nav-timefix-20260827 --format 'started={{.State.StartedAt}} restart={{.RestartCount}}'
docker exec scout-nav-timefix-20260827 bash -lc 'rostopic echo -n 1 /odom/header; rostopic echo -n 1 /amcl_pose/header'
```

### 11.3 打开诊断显示

在现有 WEB/APP 中只打开以下显示开关：

- GlobalPlanner 全局路径；
- TEB 局部路径；
- `/cmd_vel` 与 `/odom` 速度诊断。

这些开关仅订阅显示，不修改导航参数。

### 11.4 AI 使用多个有限时 SSH 会话并行观察

会话 A：

```bash
docker exec scout-nav-timefix-20260827 bash -lc 'timeout 35s rostopic echo /move_base/status' || true
```

会话 B：

```bash
docker exec scout-nav-timefix-20260827 bash -lc 'timeout 35s rostopic echo /cmd_vel' || true
```

会话 C：

```bash
docker exec scout-nav-timefix-20260827 bash -lc 'timeout 35s rostopic echo /odom' || true
```

会话 D：

```bash
docker exec scout-nav-timefix-20260827 bash -lc 'timeout 35s rosrun tf tf_echo map base_link' || true
```

现场人员随后在 RViz 发送一次 0.5–1 m 目标。不要连续点击目标。

为了避免路径 Topic 输出过大，分别在三个时间点各取一帧：

1. 目标刚发送后；
2. 小车行驶中；
3. 到达目标附近但仍持续规划时。

每次执行：

```bash
docker exec scout-nav-timefix-20260827 bash -lc 'rostopic echo -n 1 /move_base/GlobalPlanner/plan'
docker exec scout-nav-timefix-20260827 bash -lc 'rostopic echo -n 1 /move_base/TebLocalPlannerROS/local_plan'
```

如果 Topic 名不存在，先以 `rostopic list | grep -Ei "plan|teb|move_base"` 查实际名称，只读记录，不修改配置。

### 11.5 到点后的通过条件

理想结果：

- GlobalPlanner 对空旷短目标基本为直线；
- TEB 局部路径没有明显左右摆动、回环或远离目标；
- `/cmd_vel` 逐渐收敛到 `linear.x≈0`、`angular.z≈0`；
- `/odom` 速度同步回到接近零；
- move_base status 从 ACTIVE 进入 SUCCEEDED；
- 到点后不再持续发布明显非零速度指令；
- `map→base_link` 不跳变；
- 容器 `RestartCount` 不增加。

## 12. 故障分类决策树

### A. GlobalPlanner 路径本身就绕

优先检查：

1. global costmap 是否存在错误障碍；
2. 运行时 global inflation/cost scaling 是否与源码不一致；
3. 地图、origin、resolution 是否加载错误；
4. GlobalPlanner 是否读取了旧 install 参数；
5. 目标 pose 是否落在障碍或膨胀区。

不要先修改 TEB。

### B. GlobalPlanner 直，但 TEB local plan 绕

优先检查：

1. local costmap 是否有贴近 footprint 的代价点；
2. `/scan` 是否包含机器人自身点或近距离噪点；
3. footprint 尺寸与 base_link 原点；
4. local inflation 从 0.05 增至 0.10 的影响；
5. TEB 强前进、强非完整约束是否放大问题。

后续最小 A/B 候选：只回退 local inflation，不动全局参数；但必须另行授权。

### C. GlobalPlanner 和 TEB 都直，但小车绕或不停

优先检查：

1. `/cmd_vel` 与 `/odom` 的符号、比例和延迟；
2. Scout 驱动是否重复；
3. CAN 驱动实际执行是否和 `/cmd_vel` 一致；
4. odom 是否跳零或被重启；
5. 多个速度 publisher/mux 是否抢控制；
6. 底盘角速度方向是否相反。

### D. 到点附近 TF/定位跳动

优先检查：

1. 是否有双 `/odom` publisher；
2. 是否有双 `odom→base_link` broadcaster；
3. Scout 驱动是否被 FastAPI heartbeat 重启；
4. AMCL `map→odom` 是否跳变；
5. 2D AMCL 和 3D `map→camera_init` 是否同时运行；
6. `/initialpose` 是否同时触发两套定位；
7. AMCL `omni-corrected` 与非全向 Scout 是否模型不匹配。

后续最小 A/B 候选：先隔离为单一驱动和单一定位链，然后单独测试 `diff-corrected`；必须另行授权。

### E. move_base 长期 ACTIVE，但路径和 TF 基本正常

最后才检查：

- 实际位置误差是否略高于 0.12 m；
- yaw 误差是否略高于 0.15 rad；
- `complete_global_plan`；
- `global_plan_overwrite_orientation`；
- 目标 yaw 是否由 RViz 正确给出。

不要先通过大幅放宽 tolerance 掩盖 TF 或 odom 问题。

## 13. 最终报告模板

```markdown
# ROS1 2D 导航现场诊断报告

## 基本信息
- 测试时间：
- Jetson hostname：
- 容器：
- 镜像：
- Image ID：
- StartedAt：
- RestartCount 测试前/后：

## 安全声明
- 是否修改文件：NO
- 是否修改 rosparam：NO
- 是否重启/停止容器：NO
- 是否启动额外节点：NO
- 是否留下后台进程：NO

## 运行来源
- rospack find my_nav：
- rospack find scout_base：
- src/install 指纹是否一致：
- 缺失文件：
- 判定：MATCH / RUNTIME_SOURCE_MISMATCH / UNKNOWN

## 节点和 publisher
- scout_base_node 数量：
- move_base 数量：
- amcl 数量：
- /odom publishers：
- /cmd_vel publishers：
- odom→base_link broadcaster：
- transform_fusion/global_localization 是否运行：

## 运行参数
- AMCL odom_model_type：
- AMCL update/recovery 参数：
- GlobalPlanner：
- LocalPlanner：
- global inflation/scaling：
- local inflation/scaling：
- footprint：
- TEB goal tolerance/forward weight：

## 静止测试
- map→odom 稳定性：
- odom→base_link 稳定性：
- map→base_link 稳定性：
- 时间戳是否回退：
- odom 是否归零：

## 0.5–1 m 短目标时间线
- T0 发送目标：
- T1 开始移动：
- T2 接近目标：
- T3 最终状态：
- GlobalPlanner 形状：直 / 绕 / UNKNOWN
- TEB local plan：直 / 绕 / 回环 / UNKNOWN
- cmd_vel：
- odom 实际速度：
- move_base 最终 status：

## 分类
- A GlobalPlanner 已绕：YES/NO
- B GlobalPlanner 直但 TEB 绕：YES/NO
- C 两条直但底盘/位姿不收敛：YES/NO
- D TF/odom 到点跳变：YES/NO
- E 证据不足：YES/NO

## 根因排序
1.
2.
3.

## 关键原始证据
- 命令：
- 输出摘要：
- 时间：

## 下一步最小 A/B 建议
- 建议：
- 需要修改的唯一变量：
- 回滚方法：
- 风险：
- 当前是否已执行：NO
```

## 14. 测试结束检查

执行：

```bash
docker inspect scout-nav-timefix-20260827 --format 'status={{.State.Status}} started={{.State.StartedAt}} restart={{.RestartCount}}'
docker exec scout-nav-timefix-20260827 bash -lc 'ps -eo pid,args | grep -E "rostopic echo|tf_echo|tf_monitor|rosbag record" | grep -v grep || true'
```

结束标准：

- 演示容器仍是原容器、原镜像；
- 容器没有被重启；
- 没有遗留 `rostopic echo`、`tf_echo`、`tf_monitor`、`rosbag record`；
- 没有修改参数或文件；
- 报告中所有结论都有对应命令输出和绝对时间；
- 若证据冲突，标记 `NEEDS_CONFIRMATION`，禁止猜测。
