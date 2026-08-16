# 知识：系统架构（architecture）

## 目标
记录整体架构：模块关系、数据流、边界。

## 已知（2026-08-16 扫描，部分待确认）
- 前端 APP（SLAMIBotApp）↔ rosbridge（WebSocket）↔ 机器人导航系统。
- 下位机：STM32（slamibot_stm32）负责底盘/底层控制。
- 上位机/计算：Jetson Orin NX，运行 Ubuntu + ROS1（CURRENT）+ Docker。
- 后端：是否存在独立后端待确认（可能前端直连 rosbridge）。

## 数据流（待确认后固化为图/文字）
```
前端 APP --(rosbridge/WebSocket)--> ROS1 导航（Jetson）
      ^                                  |
      |                                  v
  (可选后端)                        STM32 底盘（串口）
```

## 待回填
- 各模块具体接口（见 `interfaces/`）。
- 完整拓扑与数据流细节。
