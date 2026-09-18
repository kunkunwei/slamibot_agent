# APP 地图保存/删除后的列表刷新优化交接（2026-09-05）

## 1. 目标与边界

目标：修复导航控制页中“保存地图或删除地图成功后，地图列表不立即更新，必须退出页面再进入才更新”的问题。

仅修改 Android APP：`F:\SLAMIBotApp`。不要修改导航后端接口、ROS、Docker、Jetson、地图文件格式或数据库结构；不要取消后端自动生成 `*_display.pcd` 的行为。

## 2. 已确认现场事实

- Jetson 保存的新地图 `map0905` 已立即写入数据库和宿主机目录。
- 后端地图列表接口在保存完成后已立即返回 `map0905`。
- 退出导航控制页再进入，APP 能显示新地图，说明问题位于 APP 页面状态刷新，不是后端保存失败。
- 保存时后端会保留原始 `<map>.pcd`，并自动生成 0.1m 体素的 `<map>_display.pcd` 供 APP 低带宽显示；APP 不应把它提示为“原始地图被降采样”。

## 3. 相关代码

### Controller

文件：

```text
F:\SLAMIBotApp\app\app\src\main\java\com\example\metacam\NativeNavigationController.kt
```

当前关键逻辑：

```kotlin
fun saveMap(name: String) {
    val mapName = name.trim()
    runCommand(
        "地图已保存，请在地图列表中手动降采样",
        afterSuccess = { loadMapContent(mapName) },
    ) { repository.saveMap(mapName) }
}
```

```kotlin
fun loadMapContent(preferredMapName: String = "") {
    scope.launch {
        // listMaps + points/areas/tasks/actions，然后整体替换 content
    }
}
```

```kotlin
private fun runCommand(
    successText: String,
    afterSuccess: () -> Unit = {},
    block: suspend () -> D360ApiResult,
)
```

`runCommand()` 成功后依次调用 `refreshStatus()` 和 `afterSuccess()`；但二者都会再启动异步任务，调用方不会等待地图列表更新完成。多个刷新任务可能乱序完成，旧结果可能覆盖新结果。

删除逻辑也有同类问题：

```kotlin
fun deleteMap(id: Int) = mutateMapContent("地图已删除") { repository.deleteMap(id) }

private fun mutateMapContent(...) = runCommand(...) {
    block().also { loadMapContent(mutableState.value.content.selectedMapName) }
}
```

### Repository

文件：

```text
F:\SLAMIBotApp\app\app\src\main\java\com\example\metacam\NativeNavigationRepository.kt
```

接口保持不变：

```kotlin
suspend fun listMaps()
suspend fun saveMap(mapName: String)
suspend fun deleteMap(id: Int)
```

### Screen

文件：

```text
F:\SLAMIBotApp\app\app\src\main\java\com\example\metacam\NativeNavigationScreen.kt
```

地图选择对话框直接读取：

```kotlin
state.content.maps
```

所以 Controller 必须在命令完成后可靠更新该状态，不能依赖页面重建。

## 4. 推荐实现

### 4.1 将地图内容加载拆成可等待的挂起函数

推荐结构：

```kotlin
private suspend fun fetchMapContent(preferredMapName: String = ""): NativeNavigationContentState
```

该函数只负责请求并构造新状态，不自行 `scope.launch`。

公开刷新函数可保留：

```kotlin
fun loadMapContent(preferredMapName: String = "") {
    scope.launch {
        refreshMapContentNow(preferredMapName)
    }
}
```

命令成功路径应直接在当前命令协程里：

```text
保存/删除接口完成
→ 等待 listMaps()
→ 更新 state.content.maps
→ 更新 selectedMapName
→ 再解除 commandInFlight 并显示成功提示
```

不要在 `block().also { loadMapContent(...) }` 中启动无法等待的刷新。

### 4.2 防止旧刷新覆盖新刷新

至少选择一种方案：

1. 保存/删除/切换地图等修改操作共用同一个串行 `Job`/`Mutex`；或
2. 为地图刷新增加递增 generation/requestId，仅允许最新请求写入状态；或
3. 取消上一轮地图刷新任务后再启动新任务。

推荐使用 `Mutex` 或 generation，避免页面初始化刷新和保存后的刷新乱序覆盖。

### 4.3 保存成功后的选择与提示

保存成功后：

- 重新请求地图列表；
- 若列表中存在新地图，将 `selectedMapName` 设置为新地图名；
- 地图列表对话框再次打开时立即看到新地图；
- 成功提示改为：

```text
地图已保存，3D 预览已生成
```

不要继续提示“请手动降采样”，因为后端保存阶段已经生成 `*_display.pcd`。

### 4.4 删除成功后的选择

删除成功后：

- 等待重新加载地图列表；
- 被删除地图必须立即从 `state.content.maps` 消失；
- 如果删除的是当前 UI 选中项，按以下顺序选择：
  1. 后端当前激活地图；
  2. 列表第一张地图；
  3. 无地图时设为空字符串；
- 同步清空或重新加载对应点位、区域和任务，不能保留已删除地图的旧内容。

注意：后端会拒绝删除当前激活地图或有关联数据且未确认强制删除的地图。APP 只能在后端返回成功后更新本地列表，不能先乐观删除。

## 5. 不要做的修改

- 不改变现有 HTTP 路径或 JSON 协议。
- 不在 APP 中直接操作 Jetson 文件。
- 不取消后端 `*_display.pcd` 自动生成。
- 不把显示点云降采样理解为覆盖原始 PCD。
- 不用固定延时 `delay(...)` 代替等待真实接口结果。
- 不通过退出/重进页面或 Activity 重建作为刷新方案。
- 不顺带修改增量建图算法。

## 6. 验收场景

### 保存地图

1. 进入建图模式并保存唯一名称 `app_refresh_test_1`。
2. 保存接口成功后，不退出导航控制页。
3. 立即打开地图列表。
4. 列表必须出现 `app_refresh_test_1`，且当前选中项为它。
5. 页面提示不得再要求手动降采样。

### 删除地图

1. 删除一张允许删除的非激活地图。
2. 删除接口成功后不退出页面。
3. 立即重新打开地图列表。
4. 被删地图必须消失，其他地图保持不变。
5. 如果删除的是 UI 选中地图，点位/区域/任务不得继续显示旧地图数据。

### 并发与失败

1. 保存过程中快速开关地图列表，不得出现旧列表覆盖新列表。
2. 后端返回删除失败时，APP 本地列表不得移除该地图。
3. 网络超时后重试，最终成功时应正常刷新且不重复添加。
4. 连续保存两张不同名称地图，列表顺序和选中项应与最后一次成功操作一致。

## 7. 交付要求

- 开始前记录 `git status -sb`，保留现有 `.gradle/` 等未跟踪内容，不纳入提交。
- 只提交本任务涉及的 Kotlin 文件。
- 输出修改前后刷新时序说明和 `git diff --check` 结果。
- 按用户偏好不主动构建 APK、不安装 APP：`tests: SKIPPED (APP build/install handled by user)`。
