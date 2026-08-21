---
name: scout-nav-troubleshoot-2026-08-18
description: 2026-08-18 scout-nav 容器与 nav_api DB 故障排查总结（filter-branch 丢文件 → 恢复 → bind mount sync 验证 → 后续清理挂起）
metadata:
  type: known-issue
---

# Scout 容器与地图 DB 故障排查总结（2026-08-18）

## 起由
2026-08-18 全天围绕 `scout-nav` 容器、`nav_api` 数据库与地图文件 sync 展开。
起因：filter-branch --index-filter 副作用 unlink 工作树 13 个文件（~58 MB）；
后续：DB Map 表里 22 条记录中绝大多数 yamlFilePath 是无效的，WEB 端切换地图失败。

## ✅ 已完成

### A. 文件与代码恢复
1. **13 个丢失文件恢复**：从 `F:\d360_nav2D`（HEAD=a16dc8f，未经过 filter-branch）找回并放到板上对应位置。详见 `filter-branch-unlink-side-effect-2026-08-18.md`。
2. **pcd_to_map.py 恢复到容器**（13989 B）：nav_api `_PCD_TO_MAP` 路径；从 `F:\d360_nav2D\src\my_nav\maps\pcd_to_map.py` scp 到板，bind mount 自动同步。
3. **install/ 完整备份**：172 MB，备份目录 `~/Scout_mini_navigation_install_dockerbackup_20260818_173702`（用户已清理）。
4. **12 个 recovery 文件备份**：52 MB，备份目录 `~/Scout_mini_navigation_recovery_20260818_170014`（用户已清理）。
5. **nav_api.db 备份**：`~/Scout_mini_navigation_recovery_20260818_181906/nav_api.db.bak`（用户已清理）。

### B. 数据库（DB）修正
- DB 在容器内 `/Scout_mini_navigation/src/nav_api/db/nav_api.db`（bind mount 自 host）
- DB owner = `root:root`，host 上 `jetson` 无写权限 → 所有修改通过 `docker exec -u root` 在容器内进行
- **路径批量 UPDATE**：22 条 Map 记录的 yamlFilePath / pcdFilePath 中 15 条从 `/home/jetson/...` 修正为容器内 `/Scout_mini_navigation/...`
- 修正后 4 张地图可正常切换：`dinggu7_6`、`dinggu7_7`、`dinggu7_8`、`dinggu7_9`

### C. bind mount 验证
- `/home/jetson/Scout_mini_navigation/src/my_nav/maps` → `/Scout_mini_navigation/src/my_nav/maps`（maps）
- `/home/jetson/Scout_mini_navigation/src/nav_api/db` → `/Scout_mini_navigation/src/nav_api/db`（DB）
- 容器内 `docker exec ls` 与 host 上 `ls` 看到同一份 inodes → **bind mount 实时双向同步**
- WEB UI 切换地图成功（`dinggu7_7`）= sync 工作的活体证明

### D. 容量管理（用户手动执行）
- 容器重启后根因：host 上 233 GB 磁盘 100% 已用（21 GB 备份）
- 用户已手动删除 4 个 backup 目录（恢复 ~23.4 GB）：
  - `~/Scout_mini_navigation_maps_api_only_20260818_174734` (23 GB)
  - `~/Scout_mini_navigation_install_dockerbackup_20260818_173702` (172 MB)
  - `~/Scout_mini_navigation_recovery_20260818_170014` (52 MB)
  - `~/Scout_mini_navigation_recovery_20260818_181906` (DB 备份)

## ⚠️ 挂起（明天做）

### E. DB 中"看不了的地图"未清理
- DB 中 22 条 Map 记录，4 张有效（dinggu7_6~9），其他 17 条 yamlFilePath 仍指向不存在文件
- **未跑成的原因**：heredoc 写 /tmp 失败（disk full）；用户手动腾空间后没继续用 stdin pipe 单行命令跑
- 详见下方"明天恢复的步骤"

### F. pcd_to_map.py 未实际执行
- 脚本恢复到容器内可被 nav_api 找到的位置，但**没有真实跑过** "PCD → .pgm + .yaml"
- 17 个失效 Map 记录的 PCD 文件可能在 `api_map/<name>/<name>.pcd`——若用户后续想批量转换，本脚本是入口

### G. 容器内 stale __pycache__
- `/Scout_mini_navigation/src/my_nav/maps/__pycache__/` 是 root:root owner，4 KB，可能含 Python 3.8 编译的 .pyc
- **不影响功能**（Python 用 .py 优先；.pyc 跨 Python 版本会被拒绝执行）

## 📚 关键教训（不可遗忘）

### 1. filter-branch 工作树备份规则
- `cp -a` 完整工作树（不是仅 .git）—— `.git` 不保留工作树文件
- 详细见 `filter-branch-unlink-side-effect-2026-08-18.md`

### 2. .pyc 跨 Python 版本不兼容
- Python 3.8 编译的 .pyc 在 Python 3.11.9 中加载会失败（魔法数不匹配）
- 跨机器搬运脚本必须拷贝 `.py` 源码，不能只搬 `__pycache__/`

### 3. heredoc 失败时机
- bash heredoc 写临时文件到 `/tmp` —— 当 `/` 满 100% 时直接报"无法为立即文档创建临时文件"
- **替代方案**：`echo '...' | docker exec -i <container> python3` 用 stdin pipe

### 4. 用户对"乱删"敏感
- 用户不希望 AI 在没明确授权时建议删除其文件或目录
- **下次操作前**先问、列出待删清单、给"是否继续"确认节点

## 🔧 关键事实（机器 + 路径）

- 主机：`jetson@ubuntu` (192.168.31.135)
- 容器：`scout-nav` (image: scout-nav:latest)，容器内 5000 端口**未暴露到 host**
- nav_api 入口：`http://127.0.0.1:5000`（容器内）
- nav_api 地图路由前缀：`/api/map/`
- 工作目录（host）：`/home/jetson/Scout_mini_navigation`
- 容器入口：`/Scout_mini_navigation`（镜像层）/ `src/my_nav/maps` 等在 bind mount
- 来源备份：`F:\d360_nav2D` (HEAD=a16dc8f)
- nav_api 代码路径：`src/nav_api/fastapi_service/{app.py, map_api.py, database.py, ros_client.py}`

## 明天恢复：DB 清理步骤（待用户授权）

### 第一步：列出 KEEP/DEL（stdin pipe，不写 /tmp）
```bash
echo 'import sqlite3, os
DB = "/Scout_mini_navigation/src/nav_api/db/nav_api.db"
ROOT = "/Scout_mini_navigation"
conn = sqlite3.connect(DB)
rows = list(conn.execute("SELECT id, mapName, mapType, yamlFilePath, isActive FROM Map ORDER BY id"))
keep = []
bad = []
for r in rows:
    p = r[3] or ""
    ok = bool(p) and p.startswith(ROOT) and os.path.exists(p)
    print("KEEP" if ok else "DEL", r[0], r[1], p[:60])
    (keep if ok else bad).append(r)
print("---")
print("KEEP:", len(keep), "DEL:", len(bad))
for r in bad:
    print(" ", r)
' | docker exec -u root -i scout-nav python3
```

### 第二步（清理，必须用户确认后才执行）：
- 删除 17 张无效 Map 记录 + 关联 PointPosition + TaskFlow
- 使用 `PRAGMA foreign_keys = ON` + 事务包裹
- 候选命令模板（待第一步结果填具体 id/name）：

```bash
echo '
import sqlite3
conn = sqlite3.connect("/Scout_mini_navigation/src/nav_api/db/nav_api.db")
conn.execute("PRAGMA foreign_keys = ON")
to_delete = [   # ← 由第一步输出填充
    # (id, mapName) 例: (2, "xxx"),
]
try:
    for id_, name in to_delete:
        pc = conn.execute("SELECT COUNT(*) FROM PointPosition WHERE mapName=?", (name,)).fetchone()[0]
        tc = conn.execute("SELECT COUNT(*) FROM TaskFlow WHERE mapName=?", (name,)).fetchone()[0]
        print(f"  {name}: points={pc} tasks={tc} (will be cascade-deleted)")
    for id_, name in to_delete:
        conn.execute("DELETE FROM TaskFlow WHERE mapName=?", (name,))
        conn.execute("DELETE FROM PointPosition WHERE mapName=?", (name,))
        conn.execute("DELETE FROM Map WHERE mapName=?", (name,))
        print("DEL:", name)
    conn.commit()
    print("OK: committed")
except Exception as e:
    conn.rollback()
    print("FAIL: rolled back:", e)
conn.close()
' | docker exec -u root -i scout-nav python3
```

## 关联
- 仓库：`kunkunwei/Scout_mini_navigation`
- 类似 issue：`filter-branch-unlink-side-effect-2026-08-18.md`、`web-app-map-display-2026-08-18.md`
