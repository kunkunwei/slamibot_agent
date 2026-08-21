# 接口：rosbridge（前端 ↔ ROS 的边界，protected）

> 这是前后端与 ROS 系统之间的**稳定边界**，属于 protected interface，默认禁止修改。

## 事实源
- `facts/rosbridge_profile.yaml`（唯一可信来源）

## 当前端口契约（2026-08-19）

| 调用方 | 地址 | 提供方/节点 |
|---|---|---|
| Android APP 全部 ROS 功能 | `ws://<Jetson>:9090` | core `/rosbridge_websocket` |
| 浏览器 WEB | `ws(s)://<Jetson>/rosbridge` | Nginx → 9090 |
| FastAPI/nav_api 内部 | `ws://127.0.0.1:19090` | scout-nav `/scout_nav_rosbridge` |

架构决策见 `decisions/ADR-0002-d360-dual-rosbridge-ports.md`。

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
