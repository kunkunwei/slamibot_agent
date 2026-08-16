# 知识：rosbridge

## 用途
记录 rosbridge 的用法、WebSocket 地址、Topic/Service/消息格式、状态码、迁移注意。

## 接口事实源
- `facts/rosbridge_profile.yaml`（唯一可信来源）
- `interfaces/rosbridge/`（接口契约与迁移说明）

## 关键点
- 前端 APP 通过 rosbridge（WebSocket）与 ROS 通信，这是前后端与 ROS 的稳定边界。
- 迁移时若 rosbridge 或消息类型变化，必须写独立迁移说明，不得覆盖旧协议。

## 索引
<!-- 例如：
- [rosbridge-通信调试.md](./rosbridge-通信调试.md)
-->
（暂无，待回填。）
