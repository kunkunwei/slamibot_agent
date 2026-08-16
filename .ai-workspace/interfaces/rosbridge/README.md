# 接口：rosbridge（前端 ↔ ROS 的边界，protected）

> 这是前后端与 ROS 系统之间的**稳定边界**，属于 protected interface，默认禁止修改。

## 事实源
- `facts/rosbridge_profile.yaml`（唯一可信来源）

## 应记录的内容（逐项回填）
- WebSocket 地址（`ws://...`）
- 前端订阅/发布的 Topic（名称 + 消息类型 + 方向）
- Service / 参数
- 消息格式（JSON 结构）
- 导航状态 / 任务状态编码
- 错误码约定
- 前后端与 ROS 的边界划分

## 迁移规则（ROS1 → ROS2）
- 若 rosbridge 或消息类型变化，必须新建**接口迁移说明**（如 `migration-ros1-to-ros2.md`），
  不得直接覆盖本目录的旧协议。

## 索引
<!-- 例如：
- [rosbridge-contract-v1.md](./rosbridge-contract-v1.md)
- [migration-ros1-to-ros2.md](./migration-ros1-to-ros2.md)
-->
（暂无，待回填。）
