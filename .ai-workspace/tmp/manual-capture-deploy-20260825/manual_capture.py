"""Temporary manual photo capture route for fast APP validation."""

import base64
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import roslibpy
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import Field

from .models import RequestModel, fail, ok
from .ros_client import ros_client

capture_router = APIRouter(prefix="/api/capture", tags=["手动拍照"])
files_router = APIRouter(tags=["手动拍照"])

CAPTURE_DIR = Path(
    os.environ.get(
        "CAPTURE_DIR",
        str(Path(__file__).resolve().parent.parent / "db" / "captures"),
    )
)
CAMERA_TOPIC = os.environ.get("CAMERA_TOPIC", "/SLB_CAM_B/compressed")
_FRAME_MAX_AGE_S = max(0.1, float(os.environ.get("CAMERA_FRAME_MAX_AGE_S", "3.0")))
_FIRST_FRAME_TIMEOUT_S = max(0.1, float(os.environ.get("CAMERA_FIRST_FRAME_TIMEOUT_S", "3.0")))
_SAFE_FILE = re.compile(r"^manual_[0-9]{8}_[0-9]{6}_[0-9]{6}_[0-9a-f]{8}\.jpg$")

_lock = threading.Lock()
_frame_ready = threading.Event()
_camera_topic: Optional[roslibpy.Topic] = None
_latest_frame: Optional[bytes] = None
_latest_frame_at: Optional[float] = None


class CapturePhotoRequest(RequestModel):
    source: str = Field(default="manual")
    pointName: Optional[str] = None


def _on_frame(message) -> None:
    global _latest_frame, _latest_frame_at
    raw = message.get("data") if isinstance(message, dict) else None
    try:
        if isinstance(raw, str):
            frame = base64.b64decode(raw, validate=False)
        elif isinstance(raw, (bytes, bytearray)):
            frame = bytes(raw)
        elif isinstance(raw, list):
            frame = bytes(raw)
        else:
            return
    except (TypeError, ValueError):
        return
    if len(frame) < 4 or not frame.startswith(b"\xff\xd8"):
        return
    with _lock:
        _latest_frame = frame
        _latest_frame_at = time.monotonic()
    _frame_ready.set()


def _ensure_camera_subscription() -> Optional[str]:
    global _camera_topic
    if not ros_client.is_connected:
        return "rosbridge 未连接"
    with _lock:
        if _camera_topic is not None:
            return None
        try:
            topic = roslibpy.Topic(
                ros_client._ros,
                CAMERA_TOPIC,
                "sensor_msgs/CompressedImage",
            )
            topic.subscribe(_on_frame)
            ros_client._topics.append(topic)
            _camera_topic = topic
        except Exception as exc:
            return "订阅相机话题失败: %s" % exc
    return None


def _snapshot() -> tuple[Optional[bytes], str]:
    error = _ensure_camera_subscription()
    if error:
        return None, error

    with _lock:
        frame = _latest_frame
        received_at = _latest_frame_at
    if frame is None or received_at is None or time.monotonic() - received_at > _FRAME_MAX_AGE_S:
        _frame_ready.clear()
        _frame_ready.wait(_FIRST_FRAME_TIMEOUT_S)
        with _lock:
            frame = _latest_frame
            received_at = _latest_frame_at

    if frame is None or received_at is None:
        return None, "未收到相机帧,请检查 %s" % CAMERA_TOPIC
    age = time.monotonic() - received_at
    if age > _FRAME_MAX_AGE_S:
        return None, "相机帧已过期(%.2fs),请检查 %s" % (age, CAMERA_TOPIC)
    return bytes(frame), "success"


@capture_router.post("/photo")
def capture_photo(request: CapturePhotoRequest):
    frame, message = _snapshot()
    if frame is None:
        return fail(message)

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    token = os.urandom(4).hex()
    file_name = "manual_%s_%s.jpg" % (stamp, token)
    final_path = CAPTURE_DIR / file_name
    temp_path = CAPTURE_DIR / (file_name + ".tmp")
    try:
        temp_path.write_bytes(frame)
        os.replace(temp_path, final_path)
    except Exception as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return fail("拍照保存失败: %s" % exc)

    return ok(
        {
            "id": 0,
            "fileName": file_name,
            "url": "/captures/%s" % file_name,
            "pointName": request.pointName or "",
            "source": request.source or "manual",
        }
    )


@files_router.get("/captures/{file_name}")
def read_capture(file_name: str):
    if not _SAFE_FILE.fullmatch(file_name):
        raise HTTPException(status_code=404, detail="photo not found")
    path = CAPTURE_DIR / file_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(path, media_type="image/jpeg", filename=file_name)


# Optional isolated test server; the main deployment imports only the routers above.
standalone_app = FastAPI(title="Manual Capture Temporary Service")
standalone_app.include_router(capture_router)
standalone_app.include_router(files_router)


@standalone_app.on_event("startup")
def _standalone_start() -> None:
    ros_client.start()


@standalone_app.on_event("shutdown")
def _standalone_stop() -> None:
    ros_client.stop()