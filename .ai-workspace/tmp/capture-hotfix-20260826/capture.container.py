"""Point-arrival and manual photo capture using the latest rosbridge frame."""

import logging
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import Field

from .database import get_conn
from .mcp_compat import MCPServer
from .models import ApiResponse, RequestModel, fail, ok
from .ros_client import ros_client


LOGGER = logging.getLogger(__name__)
router = APIRouter(prefix="/api/capture", tags=["点位拍照"])

CAPTURE_DIR = os.environ.get(
    "CAPTURE_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "db",
        "captures",
    ),
)
_QUEUE_STOP = object()


class CapturePhotoRequest(RequestModel):
    pointName: Optional[str] = Field(default=None, description="关联点位名")
    taskId: Optional[int] = Field(default=None, description="触发任务 ID")
    source: str = Field(default="manual", description="manual / point_action")


@dataclass(frozen=True)
class _CaptureJob:
    frame: bytes
    point_name: Optional[str]
    task_id: Optional[int]
    source: str
    arrival_id: str


class CaptureService:
    """Persist arrival photos on one bounded worker, outside ROS callbacks."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[object]" = queue.Queue(
            maxsize=max(1, int(os.environ.get("ARRIVAL_CAPTURE_QUEUE_SIZE", "16")))
        )
        self._worker: Optional[threading.Thread] = None
        self._worker_lock = threading.Lock()
        self._save_lock = threading.Lock()

    def start(self) -> None:
        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run,
                name="arrival-capture",
                daemon=True,
            )
            self._worker.start()

    def stop(self) -> None:
        with self._worker_lock:
            worker = self._worker
        if worker is None:
            return
        try:
            self._queue.put_nowait(_QUEUE_STOP)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(_QUEUE_STOP)
            except queue.Full:
                LOGGER.warning("capture worker stop signal could not be queued")
        worker.join(timeout=3)
        with self._worker_lock:
            if self._worker is worker and not worker.is_alive():
                self._worker = None

    def enqueue_arrival(self, event: dict[str, Any]) -> bool:
        frame, message = self._snapshot_frame()
        if frame is None:
            LOGGER.warning(
                "point_action photo skipped at %s: %s",
                event.get("pointName"),
                message,
            )
            return False

        self.start()
        job = _CaptureJob(
            frame=frame,
            point_name=_optional_text(event.get("pointName")),
            task_id=_optional_int(event.get("taskId")),
            source="point_action",
            arrival_id=str(event.get("arrivalId") or ""),
        )
        try:
            self._queue.put_nowait(job)
            return True
        except queue.Full:
            LOGGER.warning(
                "arrival capture queue full; photo dropped: point=%s arrivalId=%s",
                job.point_name,
                job.arrival_id,
            )
            return False

    def take_photo(
        self,
        point_name: Optional[str],
        task_id: Optional[int],
        source: str,
    ) -> ApiResponse:
        frame, message = self._snapshot_frame()
        if frame is None:
            return fail(message)
        try:
            record = self._save_record(
                frame,
                _optional_text(point_name),
                _optional_int(task_id),
                _normalize_source(source),
            )
        except Exception as exc:
            LOGGER.exception("manual capture failed")
            return fail("拍照保存失败: %s" % exc)
        return ok(record)

    def _snapshot_frame(self) -> tuple[Optional[bytes], str]:
        frame, received_at = ros_client.get_latest_frame_snapshot()
        if frame is None or received_at is None:
            return None, "未收到相机帧,请检查相机驱动与 CAMERA_TOPIC 配置"
        max_age = max(0.1, float(os.environ.get("CAMERA_FRAME_MAX_AGE_S", "2.0")))
        age = time.monotonic() - received_at
        if age > max_age:
            return None, "相机帧已过期(%.2fs),请检查相机 topic" % age
        return frame, "success"

    def _run(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is _QUEUE_STOP:
                break
            job = item
            try:
                record = self._save_record(
                    job.frame,
                    job.point_name,
                    job.task_id,
                    job.source,
                )
                LOGGER.info(
                    "point_action photo saved: point=%s file=%s arrivalId=%s",
                    job.point_name,
                    record["fileName"],
                    job.arrival_id,
                )
            except Exception:
                LOGGER.exception(
                    "point_action photo failed: point=%s arrivalId=%s",
                    job.point_name,
                    job.arrival_id,
                )

    def _save_record(
        self,
        frame: bytes,
        point_name: Optional[str],
        task_id: Optional[int],
        source: str,
    ) -> dict[str, Any]:
        os.makedirs(CAPTURE_DIR, exist_ok=True)
        with self._save_lock:
            base = time.strftime("%Y%m%d_%H%M%S")
            file_name = "%s_%s.jpg" % (base, uuid.uuid4().hex[:10])
            final_path = os.path.join(CAPTURE_DIR, file_name)
            temp_path = final_path + ".tmp"
            try:
                with open(temp_path, "wb") as handle:
                    handle.write(frame)
                    handle.flush()
                os.replace(temp_path, final_path)
                with get_conn() as conn:
                    cursor = conn.execute(
                        "INSERT INTO Captures (pointName, fileName, taskId, source) "
                        "VALUES (?,?,?,?)",
                        (point_name, file_name, task_id, source),
                    )
                    capture_id = cursor.lastrowid
            except Exception:
                for candidate in (temp_path, final_path):
                    try:
                        if os.path.exists(candidate):
                            os.remove(candidate)
                    except OSError:
                        LOGGER.warning("failed to clean incomplete capture: %s", candidate)
                raise

        return {
            "id": capture_id,
            "pointName": point_name,
            "fileName": file_name,
            "taskId": task_id,
            "source": source,
            "url": "/captures/%s" % file_name,
        }


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_source(value: Any) -> str:
    source = str(value or "manual").strip()
    return source[:64] or "manual"


capture_service = CaptureService()


def register_mcp_tools(mcp: MCPServer) -> None:
    mcp.tool(name="capture_photo")(take_photo)
    mcp.tool(name="capture_list")(list_captures)


@router.post("/photo", response_model=ApiResponse)
def take_photo(req: CapturePhotoRequest) -> ApiResponse:
    """Capture the latest non-stale camera frame and persist it."""
    return capture_service.take_photo(req.pointName, req.taskId, req.source)


@router.get("/list", response_model=ApiResponse)
def list_captures(pointName: Optional[str] = None, limit: int = 50) -> ApiResponse:
    """Return newest capture records, optionally filtered by point name."""
    safe_limit = max(1, min(int(limit), 200))
    sql = "SELECT id, pointName, fileName, taskId, source, createdTime FROM Captures"
    params: list[Any] = []
    if pointName:
        sql += " WHERE pointName = ?"
        params.append(pointName)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(safe_limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return ok(
        [
            {
                "id": row["id"],
                "pointName": row["pointName"],
                "fileName": row["fileName"],
                "taskId": row["taskId"],
                "source": row["source"],
                "createdTime": row["createdTime"],
                "url": "/captures/%s" % row["fileName"],
            }
            for row in rows
        ]
    )
