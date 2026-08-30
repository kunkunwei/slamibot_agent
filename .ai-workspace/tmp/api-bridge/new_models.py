"""Shared request/response models used by both FastAPI and MCP."""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Response envelope shared by HTTP and MCP."""

    success: bool
    msg: str = "success"
    data: Optional[T] = None


def ok(data: Any = None, msg: str = "success") -> ApiResponse[Any]:
    return ApiResponse(success=True, msg=msg, data=data)


def fail(msg: str, data: Any = None) -> ApiResponse[Any]:
    return ApiResponse(success=False, msg=msg, data=data)


class RequestModel(BaseModel):
    """Base model for public request bodies."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class PointCreateRequest(RequestModel):
    type: int = Field(description="点位类型")
    mapName: str = Field(min_length=1, description="所属地图名")
    pointName: str = Field(min_length=1, description="点位名称")
    positionX: float
    positionY: float
    positionZ: float
    orientationX: float
    orientationY: float
    orientationZ: float
    orientationW: float
    controlIp: Optional[str] = None
    controlPort: Optional[int] = None
    controlType: Optional[str] = None
    controlAddress: Optional[str] = None
    controlDelayClosure: Optional[float] = None
    action: str = ""
    actionContent: str = ""
    sort: Optional[int] = None


class PointUpdateRequest(RequestModel):
    id: int = Field(description="点位 ID")
    pointName: Optional[str] = None
    positionX: Optional[float] = None
    positionY: Optional[float] = None
    positionZ: Optional[float] = None
    orientationX: Optional[float] = None
    orientationY: Optional[float] = None
    orientationZ: Optional[float] = None
    orientationW: Optional[float] = None
    type: Optional[int] = None
    action: Optional[str] = None
    actionContent: Optional[str] = None
    sort: Optional[int] = None


class PointClearRequest(RequestModel):
    mapName: str = Field(min_length=1, description="要清空点位的地图名")


class PointListRequest(RequestModel):
    mapName: Optional[str] = Field(default=None, description="地图名；不传则返回全部")


class PointMoveRequest(RequestModel):
    id: int = Field(description="点位 ID")
    mapName: str = Field(min_length=1, description="所属地图名")


class PointDeleteRequest(RequestModel):
    id: int = Field(description="点位 ID")
    force: bool = Field(default=False, description="是否强制删除被任务引用的点位")


class PointIdRequest(RequestModel):
    id: int = Field(description="点位 ID")


class TaskPointInput(RequestModel):
    pointId: Optional[int] = None
    pointName: str = Field(min_length=1)
    type: int = 2
    order: Optional[int] = None
    isTemporary: bool = False
    positionX: Optional[float] = None
    positionY: Optional[float] = None
    positionZ: Optional[float] = None
    orientationX: Optional[float] = None
    orientationY: Optional[float] = None
    orientationZ: Optional[float] = None
    orientationW: Optional[float] = None
    action: str = ""
    actionContent: str = ""


class TaskSaveRequest(RequestModel):
    taskName: str = Field(min_length=1)
    mapName: str = Field(min_length=1)
    points: list[TaskPointInput] = Field(min_length=1)
    description: Optional[str] = None
    isEnabled: bool = True


class TaskUpdateRequest(RequestModel):
    id: int
    taskName: Optional[str] = None
    description: Optional[str] = None
    isEnabled: Optional[int] = None
    points: Optional[list[TaskPointInput]] = None


class TaskListRequest(RequestModel):
    mapName: Optional[str] = None


class TaskIdRequest(RequestModel):
    id: int


class NavExecuteRequest(RequestModel):
    taskId: int


class NavCustomRequest(RequestModel):
    pointId: int
    positionX: Optional[float] = None
    positionY: Optional[float] = None
    positionZ: float = 0.0
    orientationX: float = 0.0
    orientationY: float = 0.0
    orientationZ: Optional[float] = None
    orientationW: Optional[float] = None


class PoseRequest(RequestModel):
    positionX: float
    positionY: float
    positionZ: float
    orientationX: float
    orientationY: float
    orientationZ: float
    orientationW: float


class EmptyRequest(RequestModel):
    """Explicit empty input so MCP and HTTP share the same signature."""


class MapNameRequest(RequestModel):
    mapName: str = Field(min_length=1)


class MapSaveRequest(MapNameRequest):
    mapDisplayName: Optional[str] = None


class MapDeleteRequest(RequestModel):
    mapName: Optional[str] = None
    id: Optional[int] = None
    force: int = 0


class MapUpdateRequest(MapNameRequest):
    mapDisplayName: Optional[str] = None
    mapDescription: Optional[str] = None
    pcdFilePath: Optional[str] = None


class DefaultModeRequest(RequestModel):
    """设置默认启动模式(容器/FastAPI 重启后自动恢复)。"""
    mode: str = Field(description="idle / mapping / navigation")


# ----------------------------------------------------------------
# 动作 API 请求模型(APP 动作界面)
# - add  body NavigationAction(无 id)
# - update body NavigationAction(含 id)
# - delete body {id}
# - toggle body {id, enabled}
# - execute body {action: code}
# - stop   body 空
# ----------------------------------------------------------------


class NavigationActionAddRequest(RequestModel):
    """新增一个动作。``code`` 唯一,``enabled`` 默认 1。"""

    code: str = Field(min_length=1, description="动作唯一编码(机器名)")
    name: str = Field(min_length=1, description="动作中文名")
    category: str = Field(
        default="other",
        description="photo / chassis / other,用于 execute 分发",
    )
    description: Optional[str] = None
    enabled: int = Field(default=1, description="0=禁用 / 1=启用")


class NavigationActionUpdateRequest(RequestModel):
    """部分更新动作信息;只传要改的字段。"""

    id: int = Field(description="动作 ID")
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[int] = None


class NavigationActionDeleteRequest(RequestModel):
    id: int = Field(description="动作 ID")


class NavigationActionToggleRequest(RequestModel):
    id: int = Field(description="动作 ID")
    enabled: int = Field(description="0=禁用 / 1=启用")


class NavigationActionExecuteRequest(RequestModel):
    """执行动作,body 字段名按 APP 契约为 ``action``。"""

    action: str = Field(
        min_length=1,
        description="动作编码(对应 NavigationAction.code)",
    )
