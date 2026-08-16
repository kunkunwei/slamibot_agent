# 项目：embedded-stm32（slamibot_stm32）

> 底层固件 / IAP。已在扫描中确认存在本地仓库。

## 基本信息
- id: stm32
- name: slamibot_stm32
- repo: https://github.com/electech6/slamibot_stm32.git
- local_path: "F:\\slamibot_stm32"
- current_branch: bootloader（扫描时）
- lifecycle: CURRENT
- tech_stack: [embedded, stm32, c]

## 允许修改范围（allowed_paths）
- TODO：按具体任务声明（如某 .c/.h、某外设驱动）

## 禁止修改范围 / 受保护
- 与 ROS/导航/rosbridge 的通信协议（上下位机串口协议）
- 烧录/启动相关关键配置（除非任务授权）

## 开发流程
- 改前 `git status`、改后 `git diff` + 摘要；遵循 `core/git-safety.md`。
- 真机验证需串口/烧录，属高风险，谨慎授权。

## 事实源
- 暂无独立 facts 文件；新增协议事实时在 `interfaces/` 建文档。
