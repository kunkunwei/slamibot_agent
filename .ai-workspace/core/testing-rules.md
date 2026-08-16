# 测试与验证规则（Testing Rules）

验证优先于继续修改。任何“完成”声明必须有证据。

## 原则
- **证据先于断言**：运行验证命令并展示输出，再谈“通过”。
- **失败即停**：测试失败 → 停止继续扩大修改范围 → 记录失败原因 → 报告，不进入无限自动修复。
- **验证可复现**：记录用到的命令、环境、输入，让他人能复跑。

## 分层验证
1. 单元测试：目标模块的 `test` 目标（如 `catkin_make run_tests` / `colcon test` / 前端 `npm test`）。
2. 编译/构建：`build` 通过（见 `procedures/ros1-development.md` / `ros2-development.md`）。
3. 仿真验证：导航仿真（如需），确认预期行为。
4. 真机验证：仅当任务授权 DEPLOY 时才在 Jetson 上运行（见 `procedures/jetson-validation.md`）。

## ROS1 / ROS2 隔离的验证
- 验证 ROS1 包时，只能使用 ROS1 的命令与工作区，不得顺带改动 ROS2 环境，反之亦然。
- 记录验证的是哪个栈（`technology: ros1` 或 `ros2`）、哪个 Ubuntu/Docker 环境。

## 验证结果落盘
- 通过/失败/跳过都要写进任务条目或 `known-issues/`，不能只留在对话里。
