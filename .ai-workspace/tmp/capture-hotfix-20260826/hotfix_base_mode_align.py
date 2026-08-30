# -*- coding: utf-8 -*-
"""容器热修：对齐底盘模式 API 至 APP 新契约。

- base_mode.py：整文件替换为本地新版（含 policy/selectedBase/activeBase/detectedBase/bases 探测）
- ros_client.py：补 _latest_scout_status_at 时间戳 + get_scout_detection_snapshot()
每个 ros_client 替换都以容器原文的唯一锚点为界，失败即抛错（不写盘）。
base_mode.py 由调用方 docker cp 覆盖，本脚本只做 py_compile 校验。
"""
import sys
import py_compile

BASE = "/Scout_mini_navigation/install/lib/python3/dist-packages"
RC = BASE + "/fastapi_service/ros_client.py"
BM = BASE + "/fastapi_service/base_mode.py"

# ---------- ros_client.py：scout 探测快照 ----------
s = open(RC, encoding="utf-8").read()

repls = [
    (
        "        self._latest_scout_status: Optional[dict[str, Any]] = None",
        "        self._latest_scout_status: Optional[dict[str, Any]] = None\n"
        "        self._latest_scout_status_at: Optional[float] = None",
    ),
    (
        "    def _on_scout_status(self, message: dict[str, Any]) -> None:\n"
        "        with self._lock:\n"
        "            self._latest_scout_status = message",
        "    def _on_scout_status(self, message: dict[str, Any]) -> None:\n"
        "        with self._lock:\n"
        "            self._latest_scout_status = message\n"
        "            self._latest_scout_status_at = time.time()",
    ),
    (
        "    def get_chassis_status(self) -> dict[str, Any]:",
        "    def get_scout_detection_snapshot(self) -> Tuple[bool, Optional[float]]:\n"
        '        """Return whether a Scout status frame was seen and when."""\n'
        "        with self._lock:\n"
        "            return self._latest_scout_status is not None, self._latest_scout_status_at\n"
        "\n"
        "    def get_chassis_status(self) -> dict[str, Any]:",
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
print("OK: ros_client.py 已补 scout 探测快照")

# ---------- 校验 ----------
py_compile.compile(RC, doraise=True)
py_compile.compile(BM, doraise=True)
print("COMPILE_OK: ros_client.py + base_mode.py")
print("ALL_DONE")
