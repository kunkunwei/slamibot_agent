# 系统生命周期（System Lifecycle）

必须严格区分三套系统，绝不因某任务涉及 ROS2 就自动改/迁/重构 ROS1。

## 定义
1. **CURRENT**：当前稳定运行的 ROS1 + Ubuntu 20.04 系统。**默认保护对象，稳定基线。**
2. **MIGRATION**：正在进行的 ROS1 → ROS2 迁移项目。必须作为**独立任务 + 独立工作区**处理。
3. **TARGET**：未来 Ubuntu 22.04 + ROS2 的目标架构。仅允许在明确的迁移设计/开发任务中修改。

## 默认行为
- 所有普通导航优化、Bug 修复、功能开发，默认以 **CURRENT** 为目标。
- 不允许把 CURRENT 的工作自动升级/迁移到 MIGRATION 或 TARGET。

## 迁移任务标记（强制）
任何迁移任务必须显式声明：
```yaml
migration: true
from:
  ubuntu: 20.04
  ros: ros1
to:
  ubuntu: 22.04
  ros: ros2
```
- `migration: true` 的任务是高风险、独立、需**人工批准**的专项工程。
- 普通 ROS1 Bug 修复 / 功能开发**不得隐式触发 migration**。

## 判定规则
- 任务涉及 ROS1 代码/环境 → 属于 CURRENT，除非 `migration: true`。
- 任务涉及 ROS2 代码/环境，且目标是“把现有 ROS1 迁过去” → MIGRATION/TARGET，需专项授权。
- 任务仅是“新 ROS2 探索/原型/独立模块”，与 ROS1 基线无关 → 可作为独立 ROS2 任务，但不得触碰 ROS1。
