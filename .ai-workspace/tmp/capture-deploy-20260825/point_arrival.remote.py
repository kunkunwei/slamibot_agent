"""Dispatch ROS point-arrival events without blocking navigation callbacks."""

import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any

from .ros_client import ros_client
from .tts_service import tts_service


LOGGER = logging.getLogger(__name__)


class PointArrivalDispatcher:
    """Deduplicate arrival events and independently dispatch their text content."""

    def __init__(self) -> None:
        self._recent: "OrderedDict[str, float]" = OrderedDict()
        self._lock = threading.Lock()

    def start(self) -> None:
        ros_client.set_point_arrived_handler(self.handle)
        tts_service.start()

    def stop(self) -> None:
        ros_client.set_point_arrived_handler(None)
        tts_service.stop()

    def handle(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        if self._is_duplicate(event):
            LOGGER.info("duplicate point-arrival event ignored: %s", event)
            return

        action = str(event.get("action") or "").strip()
        content = str(event.get("actionContent") or "").strip()

        # actionContent is an independent arrival announcement channel. This
        # lets action=photo capture and speak at the same point.
        if content:
            tts_service.enqueue(content)
        elif action == "tts":
            LOGGER.warning("point action tts has empty actionContent: %s", event)

        if action and action not in {"photo", "tts"}:
            LOGGER.warning("unsupported point action ignored: %s", action)

    def _is_duplicate(self, event: dict[str, Any]) -> bool:
        task_id = event.get("taskId")
        point_index = event.get("pointIndex")
        point_name = event.get("pointName")
        key = "%s:%s:%s" % (task_id, point_index, point_name)
        now = time.monotonic()
        ttl = max(1.0, float(os.environ.get("POINT_ARRIVAL_DEDUP_TTL_S", "30")))
        with self._lock:
            while self._recent:
                oldest_key, oldest_at = next(iter(self._recent.items()))
                if now - oldest_at <= ttl:
                    break
                self._recent.pop(oldest_key, None)
            if key in self._recent:
                return True
            self._recent[key] = now
            while len(self._recent) > 128:
                self._recent.popitem(last=False)
        return False


point_arrival_dispatcher = PointArrivalDispatcher()
