# 流程：新功能开发（new-feature）

## 阶段
1. **Explorer（只读）**：摸清现状——涉及哪些文件/接口/Topic，产出「事实 + 假设 + 建议 scope」。
2. **写任务**：在 `tasks/current.md` 建任务条目（见下方模板），明确 scope / forbidden / validation。
3. **Implementer（受限修改）**：改前 `git status` → 在 scope 内修改 → 改后 `git diff` + 摘要。
4. **Validator（只读验证）**：编译/测试/仿真/真机验证；失败即停并报告。
5. **落盘**：结果写回任务条目，接口/事实变更同步 `facts/` 与 `interfaces/`。

## 复杂任务模板（复制到 tasks/current.md）
```yaml
- id: TASK-2026-08-16-001
  goal: <一句话目标>
  project: navigation-ros1
  technology: ros1
  ubuntu: "20.04"
  lifecycle: CURRENT
  scope:
    - <允许修改的文件/目录>
  forbidden:
    - ros2/
    - docker/
    - rosbridge interface
    - frontend/
  dependencies: []
  validation:
    - build
    - unit test
    - navigation simulation
    - real robot test   # 仅授权时
  rollback: <如何回退>
  status: backlog        # backlog / in_progress / verifying / done
  notes: ""
```
