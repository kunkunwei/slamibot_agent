# 流程：新增机器人型号（add-new-robot）

## 步骤
1. 在 `facts/robot_profile.yaml` 增加新机型条目，未知字段标 `UNKNOWN` / `NEEDS_CONFIRMATION`。
2. 在 `knowledge/robot-platforms/` 为该机型建文档（Frame/TF、传感器、运动模型、Ubuntu/ROS 版本）。
3. 若引入新导航栈，新建 `facts/navigation_ros1_profile.yaml` / `navigation_ros2_profile.yaml` 对应条目或新文件。
4. 在 `facts/repos.yaml` 登记新仓库（remote_url / local_path / stack / status）。
5. 在 `projects/` 建对应项目目录与 `project.md`。

## 铁律
- 新机型默认遵循全局生命周期规则：ROS1 仍是默认基线；ROS2 作为独立目标。
- 不猜测传感器/F rame/参数，先读仓库与实机再回填。
