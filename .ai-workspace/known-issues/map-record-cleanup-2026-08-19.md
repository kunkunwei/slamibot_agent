---
id: map-record-cleanup-2026-08-19
title: 前端显示无可用 2D 文件的地图记录
date: 2026-08-19
status: PARTIALLY_RESOLVED
technology: ros1 + sqlite
related_repo: Scout_mini_navigation
---

# 前端地图记录与磁盘 2D 文件不一致

## 现象

`/app/points` 会列出数据库 `Map` 表中的记录，其中部分记录没有可加载的 YAML+PGM 组合，用户
无法在前端正常使用或删除。

## 根因

数据库记录和 `/home/jetson/Scout_mini_navigation/src/my_nav/maps/` 的恢复状态不一致：有些记录
未声明 `yamlFilePath`，有些路径指向已缺失的基础文件，但磁盘上可能仍有 PCD、同名前缀文件或
其它变体。仅按数据库字段或仅按目录名判断都会误删。

## 2026-08-19 已执行操作

操作前创建数据库备份：

`/home/jetson/Scout_mini_navigation/src/nav_api/db/nav_api.db.pre-map-cleanup-20260819_141713.bak`

数据库 `Map` 表删除五条记录：

| id | mapName | 删除依据 | 文件处理 |
|---:|---|---|---|
| 7 | `office_room_test` | 数据库未声明 YAML 路径 | 同名 YAML+PGM 实际存在，文件保留；记录可从备份恢复 |
| 8 | `office_room_test123` | 记录指向的目录内基础 YAML/PGM 缺失 | 未删除其它同名前缀变体 |
| 9 | `office_room_test3` | 记录指向的基础 YAML/PGM 缺失 | 目录内 `_map` 变体保留 |
| 26 | `测试1` | 无 YAML、无点位/任务/区域 | PCD 目录移动到隔离区 |
| 27 | `测试2` | 无 YAML、无点位/任务/区域 | PCD 目录移动到隔离区 |

隔离区：

`/home/jetson/Scout_mini_navigation/src/my_nav/maps/.quarantine/maps-without-2d-20260819_141713/`

其中有 `测试1/测试1.pcd`、`测试1/测试1_display.pcd`、`测试2/测试2.pcd`，属于可恢复移动，
不是永久删除。

数据库清理还把活跃地图从 `cs1` 切换为 `slam_map`。清理前后其它表
`PointPosition`、`TaskFlow`、`TaskPoint`、`Area`、`CycleConfig` 无增删改；两个数据库的
`PRAGMA integrity_check` 均为 `ok`。

## 未删除与待确认

- `test_map` 的 YAML 路径 `/path/to/test_map.yaml` 不可用，但仍关联 8 个点位、5 个任务和
  12 个任务点。为避免未经确认的级联删除，记录仍保留。
- `cs1` 的 YAML+PGM 存在，记录和文件均保留。
- `office_room_test` 的实际 YAML+PGM 存在，但数据库记录已删除。若仍需在前端使用，应从备份
  精确恢复 id=7 记录，而不是重建或覆盖整库。

## 后续防护

地图清理工具应同时校验数据库路径、YAML 的 `image` 引用、PGM 实际存在性以及关联点位/任务；
有任何关联数据时必须要求人工确认级联策略。删除前始终备份 SQLite，磁盘文件优先移动到带时间戳
隔离目录。

## 回滚

不得在 FastAPI 写库期间直接覆盖当前数据库。恢复前应停止写入、再备份当前库，并按需恢复指定
`Map` 行或从隔离区移回指定目录。
