# 流程：ROS1 → ROS2 迁移（ros1-to-ros2-migration）

> ⚠️ 高风险、独立、需**人工批准**的专项工程。绝不自动发生，绝不隐式触发。

## 前置条件（缺一不可）
1. 任务显式 `migration: true`，并写明 from/to：
```yaml
migration: true
from: { ubuntu: "20.04", ros: ros1 }
to:   { ubuntu: "22.04", ros: ros2 }
```
2. 人工明确授权（在对话中确认）。
3. 独立的迁移工作区 / 分支，与 ROS1 基线隔离。

## 阶段
1. **迁移设计（Explorer + 人工）**：盘点 Node/Topic/TF/参数/依赖，产出迁移映射表（ROS1↔ROS2）。
2. **接口迁移说明**：若 rosbridge 或消息类型变化，在 `interfaces/rosbridge/` 新建迁移说明，**不覆盖旧协议**。
3. **分步实施（Implementer）**：小步迁移、小步验证，每步可回滚。
4. **验证（Validator）**：逐节点/逐 Topic 验证，真机并行测试（新旧隔离）。
5. **收尾**：更新 `facts/navigation_ros2_profile.yaml`、ADR（`decisions/`）、`known-issues/`。

## 铁律
- 迁移期间 CURRENT（ROS1）保持稳定，不得被迁移工作破坏。
- 每个迁移子任务仍遵循 git-safety 与 change-policy。
- 未获人工批准前，任何 Agent 不得自行开始迁移。
