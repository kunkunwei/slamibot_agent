# -*- coding: utf-8 -*-
"""容器热修：为 scout-nav 容器 fastapi_service 补拍照功能依赖。

- ros_client.py：补相机缓存（_on_frame / start_camera_cache / get_latest_frame_snapshot）
- app.py：挂载 capture_router + /captures 静态 + register_capture_tools + start_camera_cache
- db/schema.sql：追加 Captures 表
每个替换都以容器原文的唯一锚点为界，失败即抛错（不写盘），确保零误伤。
"""
import sys

BASE = "/Scout_mini_navigation/install/lib/python3/dist-packages"
RC = BASE + "/fastapi_service/ros_client.py"
APP = BASE + "/fastapi_service/app.py"
SCHEMA = BASE + "/db/schema.sql"


def apply(path, repls, description):
    s = open(path, encoding="utf-8").read()
    for old, new in repls:
        count = s.count(old)
        if count != 1:
            raise RuntimeError(
                "%s: 锚点匹配 %d 次(应为 1): %r" % (path, count, old[:60])
            )
        s = s.replace(old, new, 1)
    open(path, "w", encoding="utf-8").write(s)
    print("OK: %s (%s)" % (path, description))


# ---------- 1) ros_client.py：相机缓存 ----------
CAMERA_BLOCK = '''    def _on_frame(self, message: dict[str, Any]) -> None:
        raw = message.get("data")
        try:
            if isinstance(raw, str):
                frame = base64.b64decode(raw)
            elif isinstance(raw, (bytes, bytearray)):
                frame = bytes(raw)
            elif isinstance(raw, list):
                frame = bytes(raw)
            else:
                return
        except (TypeError, ValueError):
            LOGGER.warning("invalid compressed camera frame payload")
            return
        if not frame:
            return
        with self._lock:
            self._latest_frame = frame
            self._latest_frame_at = time.monotonic()

    def start_camera_cache(self) -> None:
        """Idempotently subscribe to the compressed camera topic for captures."""
        if not self.is_connected:
            LOGGER.warning("camera frame cache not started: rosbridge disconnected")
            return
        if self._camera_topic is not None:
            return
        topic_name = os.environ.get("CAMERA_TOPIC", "/SLB_CAM_B/compressed")
        try:
            topic = self._subscribe(
                topic_name,
                "sensor_msgs/CompressedImage",
                self._on_frame,
            )
        except Exception as exc:
            LOGGER.warning("camera frame cache start failed on %s: %s", topic_name, exc)
            return
        self._camera_topic = topic
        self._topics.append(topic)
        LOGGER.info("camera frame cache started on %s", topic_name)

    def get_latest_frame_snapshot(self) -> Tuple[Optional[bytes], Optional[float]]:
        """Return an immutable copy of the latest JPEG and its monotonic timestamp."""
        with self._lock:
            frame = bytes(self._latest_frame) if self._latest_frame is not None else None
            received_at = self._latest_frame_at
        return frame, received_at

'''

apply(RC, [
    (
        "import logging\nimport os\nimport json\nimport threading\nfrom typing import Any, Optional, Tuple\n\nimport roslibpy",
        "import base64\nimport logging\nimport os\nimport json\nimport threading\nimport time\nfrom typing import Any, Optional, Tuple\n\nimport roslibpy",
    ),
    (
        "        self._teleop_topic: Optional[roslibpy.Topic] = None\n        self._lock = threading.Lock()",
        "        self._teleop_topic: Optional[roslibpy.Topic] = None\n        self._camera_topic: Optional[roslibpy.Topic] = None\n        self._latest_frame: Optional[bytes] = None\n        self._latest_frame_at: Optional[float] = None\n        self._lock = threading.Lock()",
    ),
    (
        "    def stop(self) -> None:\n        for topic in self._topics:\n            topic.unsubscribe()\n        with self._lock:",
        "    def stop(self) -> None:\n        for topic in self._topics:\n            topic.unsubscribe()\n        self._camera_topic = None\n        with self._lock:",
    ),
    (
        "ros_client = RosbridgeClient()",
        CAMERA_BLOCK + "ros_client = RosbridgeClient()",
    ),
], "相机缓存")

# ---------- 2) app.py：挂载拍照路由 ----------
apply(APP, [
    (
        "from fastapi.responses import JSONResponse\n",
        "from fastapi.responses import JSONResponse\nfrom fastapi.staticfiles import StaticFiles\n",
    ),
    (
        "from .area import register_mcp_tools as register_area_tools\n",
        "from .capture import CAPTURE_DIR\nfrom .capture import register_mcp_tools as register_capture_tools\nfrom .capture import router as capture_router\nfrom .area import register_mcp_tools as register_area_tools\n",
    ),
    (
        "register_teleop_tools(mcp)\n",
        "register_teleop_tools(mcp)\nregister_capture_tools(mcp)\n",
    ),
    (
        "    init_db()\n    ros_client.start()\n",
        "    init_db()\n    ros_client.start()\n    ros_client.start_camera_cache()\n",
    ),
    (
        "app.include_router(base_mode_router)\n\n\n# Keep this last: Mount(\"/\") is a catch-all route.",
        "app.include_router(base_mode_router)\napp.include_router(capture_router)\n\n\n# 照片静态回读必须位于 MCP 根路径兜底挂载之前。\napp.mount(\n    \"/captures\",\n    StaticFiles(directory=CAPTURE_DIR, check_dir=False),\n    name=\"captures\",\n)\n\n\n# Keep this last: Mount(\"/\") is a catch-all route.",
    ),
], "app 挂载")

# ---------- 3) schema.sql：追加 Captures 表 ----------
CAPTURES_TABLE = '''
-- ============================================================
-- Captures 拍照记录表
-- 点位到点自动拍照 / 手动拍照的存档;文件实体在 CAPTURE_DIR,此处存元数据。
-- ============================================================
CREATE TABLE IF NOT EXISTS Captures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pointName   TEXT,                                           -- 关联点位名(手动拍照可为空)
    fileName    TEXT    NOT NULL,                               -- CAPTURE_DIR 下的文件名
    taskId      INTEGER,                                        -- 触发任务 ID(到点自动拍照时)
    source      TEXT    NOT NULL DEFAULT 'manual',              -- manual / point_action
    createdTime TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
'''

s = open(SCHEMA, encoding="utf-8").read()
s = s.rstrip() + "\n" + CAPTURES_TABLE
open(SCHEMA, "w", encoding="utf-8").write(s)
print("OK: %s (Captures 表追加)" % SCHEMA)

print("ALL_DONE")
