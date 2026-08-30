# -*- coding: utf-8 -*-
"""容器热修：接通点位到达自动拍照链路。

- point_arrival.py：由调用方 docker cp 上传（精简版，去 tts_service 依赖）
- ros_client.py：补 point_arrived 订阅 + handler 字段 + 方法（唯一锚点）
- app.py：补 import + lifespan start/stop（唯一锚点）
锚点唯一性校验，失败即抛错不写盘。
"""
import py_compile

BASE = "/Scout_mini_navigation/install/lib/python3/dist-packages"
RC = BASE + "/fastapi_service/ros_client.py"
A = BASE + "/fastapi_service/app.py"
PA = BASE + "/fastapi_service/point_arrival.py"

# ---------- ros_client.py：point_arrived 订阅 ----------
s = open(RC, encoding="utf-8").read()

repls = [
    # 1) import Callable
    (
        "from typing import Any, Optional, Tuple",
        "from typing import Any, Callable, Optional, Tuple",
    ),
    # 2) __init__ handler 字段
    (
        "        self._latest_frame_at: Optional[float] = None",
        "        self._latest_frame_at: Optional[float] = None\n"
        "        self._point_arrived_handler: Optional[Callable[[dict[str, Any]], None]] = None",
    ),
    # 3) start() 订阅 point_arrived
    (
        '            self._subscribe(\n'
        '                "/battery", "sensor_msgs/BatteryState", self._on_battery\n'
        "            ),",
        '            self._subscribe(\n'
        '                "/battery", "sensor_msgs/BatteryState", self._on_battery\n'
        "            ),\n"
        "            self._subscribe(\n"
        '                "/nav_multi/point_arrived", "std_msgs/String", self._on_point_arrived\n'
        "            ),",
    ),
    # 4) 方法：_on_point_arrived + set_point_arrived_handler（挂在 _on_battery 后）
    (
        "    def _on_battery(self, message: dict[str, Any]) -> None:\n"
        "        with self._lock:\n"
        "            self._latest_battery = message",
        "    def _on_battery(self, message: dict[str, Any]) -> None:\n"
        "        with self._lock:\n"
        "            self._latest_battery = message\n"
        "\n"
        "    def _on_point_arrived(self, message: dict[str, Any]) -> None:\n"
        '        try:\n'
        '            event = json.loads(message["data"])\n'
        "        except (KeyError, TypeError, ValueError):\n"
        '            LOGGER.warning("invalid /nav_multi/point_arrived payload: %s", message)\n'
        "            return\n"
        "        if not isinstance(event, dict):\n"
        '            LOGGER.warning("invalid /nav_multi/point_arrived event: %s", event)\n'
        "            return\n"
        "        with self._lock:\n"
        "            handler = self._point_arrived_handler\n"
        "        if handler is None:\n"
        "            return\n"
        "        try:\n"
        "            handler(event)\n"
        "        except Exception:\n"
        '            LOGGER.exception("point-arrival handler failed: %s", event)\n'
        "\n"
        "    def set_point_arrived_handler(\n"
        "        self, handler: Optional[Callable[[dict[str, Any]], None]]\n"
        "    ) -> None:\n"
        "        with self._lock:\n"
        "            self._point_arrived_handler = handler",
    ),
]
for old, new in repls:
    count = s.count(old)
    if count != 1:
        raise RuntimeError(
            "ros_client.py 锚点匹配 %d 次(应为 1): %r" % (count, old[:60])
        )
    s = s.replace(old, new, 1)
open(RC, "w", encoding="utf-8").write(s)
print("OK: ros_client.py 已补 point_arrived 订阅 + handler")

# ---------- app.py：挂载 point_arrival ----------
a = open(A, encoding="utf-8").read()

a_repls = [
    # 1) import
    (
        "from .point import register_mcp_tools, router as point_router",
        "from .point import register_mcp_tools, router as point_router\n"
        "from .point_arrival import point_arrival_dispatcher",
    ),
    # 2) lifespan start
    (
        "    init_db()\n    ros_client.start()",
        "    init_db()\n    point_arrival_dispatcher.start()\n    ros_client.start()",
    ),
    # 3) lifespan stop
    (
        '            logging.warning("lifespan: 停止 ros_client 异常: %s", exc)',
        '            logging.warning("lifespan: 停止 ros_client 异常: %s", exc)\n'
        "        try:\n"
        "            point_arrival_dispatcher.stop()\n"
        "        except Exception as exc:\n"
        '            logging.warning("lifespan: 停止 point_arrival 异常: %s", exc)',
    ),
]
for old, new in a_repls:
    count = a.count(old)
    if count != 1:
        raise RuntimeError("app.py 锚点匹配 %d 次(应为 1): %r" % (count, old[:60]))
    a = a.replace(old, new, 1)
open(A, "w", encoding="utf-8").write(a)
print("OK: app.py 已挂载 point_arrival_dispatcher")

# ---------- 校验 ----------
py_compile.compile(RC, doraise=True)
py_compile.compile(A, doraise=True)
py_compile.compile(PA, doraise=True)
print("COMPILE_OK: ros_client.py + app.py + point_arrival.py")
print("ALL_DONE")
