# -*- coding: utf-8 -*-
"""容器部署: app.py 插入 restore_default_mode + 建 SystemConfig 表 + 语法校验。

不重启 FastAPI;重启由后续步骤执行,以便在验证前确认不会打断进行中的建图。
"""
import sys

BASE = "/Scout_mini_navigation/install/lib/python3/dist-packages"
A = BASE + "/fastapi_service/app.py"

# 1) app.py: init_db() 后插入 restore_default_mode(锚点唯一性校验)
s = open(A, encoding="utf-8").read()
old = (
    "    init_db()\n"
    "    point_arrival_dispatcher.start()\n"
    "    ros_client.start()"
)
new = (
    "    init_db()\n"
    "    # 恢复持久化的默认启动模式:容器/FastAPI 重启后自动进入默认模式,\n"
    "    # 让 /map 2D 栅格地图无需手动切换导航模式即可出现。\n"
    "    # 非致命:启动初期 ROS 时间(/clock)未就绪时 switch 会 fail-fast,\n"
    "    # 失败仅打日志,由容器自检守护(nav-healthcheck.sh)周期兜底。\n"
    "    try:\n"
    "        mode_ok, mode_msg = process_manager.restore_default_mode()\n"
    "        if not mode_ok:\n"
    "            logging.warning(\"lifespan: 恢复默认模式失败: %s\", mode_msg)\n"
    "    except Exception as exc:\n"
    "        logging.warning(\"lifespan: 恢复默认模式异常: %s\", exc)\n"
    "    point_arrival_dispatcher.start()\n"
    "    ros_client.start()"
)
count = s.count(old)
if count != 1:
    raise RuntimeError("app.py 锚点匹配 %d 次(应为 1): %r" % (count, old[:50]))
s = s.replace(old, new, 1)
open(A, "w", encoding="utf-8").write(s)
print("OK: app.py 已插入 restore_default_mode")

# 2) 建 SystemConfig 表(容器 DB 已存在,重跑 init_db 只补缺表,安全)
sys.path.insert(0, BASE)
from fastapi_service.database import DB_PATH, init_db  # noqa: E402
init_db()
print("OK: init_db 完成 (SystemConfig 表已创建), DB=%s" % DB_PATH)

# 3) 语法校验
import py_compile  # noqa: E402
for f in [
    A,
    BASE + "/fastapi_service/process_manager.py",
    BASE + "/fastapi_service/control.py",
    BASE + "/fastapi_service/models.py",
    BASE + "/scripts/launch_manager.py",
]:
    py_compile.compile(f, doraise=True)
print("COMPILE_OK")
print("ALL_DONE")
