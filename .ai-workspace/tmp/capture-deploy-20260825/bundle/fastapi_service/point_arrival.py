"""Dispatch ROS point-arrival events without blocking navigation callbacks."""

import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any

from .capture import capture_service
from .ros_client import ros_client
from .tts_service import tts_service


LOGGER = logging.getLogger(__name__)


class PointArrivalDispatcher:
    """Deduplicate one ROS event, then fan out photo and TTS independently."""

    def __init__(self) -> None:
        self._seen_ids: "OrderedDict[str, None]" = OrderedDict()
        self._legacy_recent: "OrderedDict[str, float]" = OrderedDict()
        self._lock = threading.Lock()

    def start(self) -> None:
        capture_service.start()
        tts_service.start()
        ros_client.set_point_arrived_handler(self.handle)

    def stop(self) -> None:
        ros_client.set_point_arrived_handler(None)
        capture_service.stop()
        tts_service.stop()

    def handle(self, event: dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        if self._is_duplicate(event):
            LOGGER.info("duplicate point-arrival event ignored: %s", event)
            return

        action = str(event.get("action") or "").strip().lower()
        content = str(event.get("actionContent") or "").strip()

        if action == "photo":
            capture_service.enqueue_arrival(event)
        elif action and action != "tts":
            LOGGER.warning("unsupported point action ignored: %s", action)

        # actionContent is independent from action, so a photo point can also speak.
        if content:
            tts_service.enqueue(content)
        elif action == "tts":
            LOGGER.warning("point action tts has empty actionContent: %s", event)

    def _is_duplicate(self, event: dict[str, Any]) -> bool:
        arrival_id = str(event.get("arrivalId") or "").strip()
        max_seen = max(16, int(os.environ.get("POINT_ARRIVAL_DEDUP_CACHE_SIZE", "256")))
        with self._lock:
            if arrival_id:
                if arrival_id in self._seen_ids:
                    return True
                self._seen_ids[arrival_id] = None
                while len(self._seen_ids) > max_seen:
                    self._seen_ids.popitem(last=False)
                return False

            # Backward compatibility for older ROS publishers without arrivalId.
            # Keep this window deliberately short so rapid task reruns are not lost.
            key = "%s:%s:%s:%s" % (
                event.get("runId"),
                event.get("taskId"),
                event.get("pointIndex"),
                event.get("pointName"),
            )
            now = time.monotonic()
            ttl = max(
                0.1,
                float(os.environ.get("POINT_ARRIVAL_LEGACY_DEDUP_TTL_S", "2.0")),
            )
            while self._legacy_recent:
                oldest_key, oldest_at = next(iter(self._legacy_recent.items()))
                if now - oldest_at <= ttl:
                    break
                self._legacy_recent.pop(oldest_key, None)
            if key in self._legacy_recent:
                return True
            self._legacy_recent[key] = now
            while len(self._legacy_recent) > max_seen:
                self._legacy_recent.popitem(last=False)
        return False


point_arrival_dispatcher = PointArrivalDispatcher()
