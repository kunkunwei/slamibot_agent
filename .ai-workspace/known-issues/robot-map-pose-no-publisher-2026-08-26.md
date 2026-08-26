# /robot_map_pose 无发布者：文档承诺"后端转发"从未实现，现已补上

- 状态: **open（代码已部署，等 /amcl_pose 有消息后生效）**（2026-08-26）
- 技术栈: ROS1 Noetic / FastAPI（uvicorn :5000）/ roslibpy / rosbridge（容器 19090 `/scout_nav_rosbridge`）
- 影响面: APP 3D 点云地图中的机器人三角箭头不更新

## 现象
- 用户操作后 APP 3D 点云地图里的箭头不动。
- `rostopic info /robot_map_pose` → `Publishers: None`（或 `Unknown topic`）。

## 根因（已确认）
- 全局（gitee master、板上 src、板上 install）**没有任何代码发布 `/robot_map_pose`**（geometry_msgs/PoseStamped）。
- README/API 文档声称"后端把 `/amcl_pose` 转发为 `/robot_map_pose`"，**但从未实现**。
- 本地 `F:\d360_nav2D\src\nav_api\fastapi_service\ros_client.py` 已补 27 行转发（`_on_pose` 末尾调 `_publish_robot_map_pose`，将 /amcl_pose 转成 PoseStamped 发 /robot_map_pose）。

## 已完成的部署（2026-08-26）
- 本地 `F:\d360_nav2D\src\nav_api\fastapi_service\ros_client.py` +27 行（`git diff` 已确认，未提交到 git）。
- **只把转发 27 行**同步到板上两份（最小改动）：
  - `/home/jetson/Scout_mini_navigation/src/nav_api/fastapi_service/ros_client.py`
  - `/home/jetson/Scout_mini_navigation/install/lib/python3/dist-packages/fastapi_service/ros_client.py`
  - 补丁基准：`F:\slamibot_agent\.ai-workspace\tmp\capture-hotfix-20260826\board_rosclient\patch_robot_map_pose.py`（把板上版 + 27 行转发 → patched）
- **容器已重启**：`docker restart scout-nav`，uvicorn PID 175 运行中。
- 板上两份 `grep -c robot_map_pose` = 11，`python3 -m py_compile` 通过。

## 为什么还没有发布者（关键）
- roslibpy 的 Topic 对象**只在 `publish()` 时才在 ROS master 注册**。
- 转发只发生在收到 `/amcl_pose` 消息时（`_on_pose` → `_publish_robot_map_pose`）。
- 当前 `/amcl_pose` 无消息（因为 `/scan` 断链 → AMCL 无定位，见 `known-issues/robot-state-publisher-exits-scan-broken-2026-08-26.md`）。
- **所以 `/robot_map_pose` 要出现发布者，必须先恢复 `/scan` → AMCL → `/amcl_pose`**。代码已就位，等定位恢复即触发。

## 关键事实：容器实际 import 哪个 ros_client.py
- 容器 import **install 版**：`/Scout_mini_navigation/install/lib/python3/dist-packages/fastapi_service/ros_client.py`。
- 板上 src = install（git diff 无差异），本地版比板上多 34 行 = 27 行转发 + 7 行 `get_scout_detection_snapshot`（板上 `base_mode.py` 不调用，为最小改动未上板）。

## 验证命令
```bash
rostopic info /robot_map_pose     # 恢复 /scan 后应显示 Publisher（rosbridge/uvicorn）
rostopic echo /robot_map_pose -n 1  # 看内容是否为 PoseStamped（frame_id=map）
```

## 注意
- 用户曾粘贴一份"简化版" ros_client.py（无 teleop/camera/point_arrived），**那是历史旧版，不是板上运行版**，勿据此改代码。
- 本地复杂版（含 teleop/camera/point_arrived）才是板上真实运行版。

## 关联
- `known-issues/robot-state-publisher-exits-scan-broken-2026-08-26.md`
- 任务 `TASK-2026-08-26-001`
