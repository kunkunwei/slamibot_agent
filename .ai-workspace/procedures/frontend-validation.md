# 流程：前端验证（frontend-validation）

## 范围
- 前端功能验证：导航控制面板、状态监控、任务下发等。
- 通过 rosbridge 打通前后端与 ROS 的联调。

## 步骤
1. **接口核对**：先读 `facts/rosbridge_profile.yaml` 与 `facts/frontend_api.yaml`，确认 Topic/消息/状态码。
2. **构建/运行**：按 `facts/frontend_api.yaml` 的 framework 构建。
3. **联调**：连接 rosbridge（WebSocket），验证订阅/发布、状态回传。
4. **真机/仿真**：与导航联调时遵循 `jetson-validation.md` 的权限分级。

## 规则
- 前端必须依赖接口定义，不直接依赖 ROS1/ROS2 内部实现。
- 接口变更先改事实源与 `interfaces/`，再改代码。
