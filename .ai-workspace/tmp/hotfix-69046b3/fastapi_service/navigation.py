"""Navigation APIs shared by FastAPI and MCP."""

from fastapi import APIRouter

from .base_mode import base_mode_manager
from .control_ownership import navigation_allowed
from . import process_manager
from .database import get_conn
from .mcp_compat import MCPServer
from .models import ApiResponse, NavCustomRequest, NavExecuteRequest, fail, ok
from .ros_client import ros_client


router = APIRouter(prefix="/api/map", tags=["导航控制"])


def register_mcp_tools(mcp: MCPServer) -> None:
    mcp.tool(name="execute_navigation_task")(nav_execute)
    mcp.tool(name="pause_navigation")(nav_pause)
    mcp.tool(name="resume_navigation")(nav_resume)
    mcp.tool(name="cancel_navigation")(nav_cancel)
    mcp.tool(name="get_navigation_status")(nav_status)
    mcp.tool(name="navigate_to_point")(nav_custom)


def _first_nonempty(primary, fallback) -> str:
    """Return a task-point override, otherwise the saved point default."""
    for value in (primary, fallback):
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def _check_conflict():
    status = ros_client.get_nav_status()
    if status["state"] in ("RUNNING", "PAUSED"):
        return "当前有任务正在执行(state=%s),请先取消" % status["state"]
    return None


def _send_task(task_id: int, task_name: str, points: list[dict]) -> ApiResponse:
    allowed, reason = navigation_allowed()
    launch_status = process_manager.get_status()
    if not allowed:
        return fail("当前控制权禁止自动导航: %s" % reason)
    if launch_status.get("mode_switching") or launch_status.get("current_mode") == "mapping":
        return fail("建图模式或模式切换期间禁止下发导航任务")
    # 导航下发前必须确保底盘处于自动模式 (SCOUT) 且 ready;
    # 复用 base_mode_manager.ensure_auto() 走与手动切换同一条安全路径
    # (disable teleop -> CAN 自检 -> roslaunch -> scout_status 校验),
    # 失败直接返回 fail, 不下发任务, 避免任务运行在底盘不可用状态下。
    ensure_resp = base_mode_manager.ensure_auto()
    if not getattr(ensure_resp, "success", False):
        return fail(
            "底盘未处于自动模式, 已阻止下发: %s"
            % getattr(ensure_resp, "msg", "BASE_MODE_NOT_READY")
        )
    success, message = ros_client.start_nav_task(task_id, task_name, points)
    return ok(None, message) if success else fail(message)


@router.post("/nav_multi/execute", response_model=ApiResponse)
@router.post("/task/execute", response_model=ApiResponse)
def nav_execute(request: NavExecuteRequest) -> ApiResponse:
    """执行数据库中保存的多点导航任务。"""
    conflict = _check_conflict()
    if conflict:
        return fail(conflict)

    with get_conn() as conn:
        task = conn.execute(
            "SELECT t.id, t.taskName, t.mapName, t.isEnabled FROM TaskFlow t JOIN Map m ON m.mapName = t.mapName AND m.isActive = 1 WHERE t.id = ?",
            (request.taskId,),
        ).fetchone()
        if task is None:
            return fail("任务不存在: taskId=%s" % request.taskId)
        if not task["isEnabled"]:
            return fail("任务已禁用,无法执行")

        rows = conn.execute(
            "SELECT tp.id, tp.pointName, tp.isTemporary, tp.pointId, tp.pointOrder, "
            "tp.positionX, tp.positionY, tp.positionZ, "
            "tp.orientationX, tp.orientationY, tp.orientationZ, tp.orientationW, "
            "tp.action AS tp_action, tp.actionContent AS tp_action_content, "
            "pp.positionX AS pp_x, pp.positionY AS pp_y, pp.positionZ AS pp_z, "
            "pp.orientationX AS pp_ox, pp.orientationY AS pp_oy, "
            "pp.orientationZ AS pp_oz, pp.orientationW AS pp_ow, "
            "pp.action AS pp_action, pp.actionContent AS pp_action_content "
            "FROM TaskPoint tp LEFT JOIN PointPosition pp ON pp.id = tp.pointId "
            "WHERE tp.taskId = ? ORDER BY tp.pointOrder, tp.id",
            (request.taskId,),
        ).fetchall()
        if not rows:
            return fail("任务中没有点位")

        points = []
        invalid = []
        for row in rows:
            if row["isTemporary"]:
                prefix = ""
            elif row["pp_x"] is None:
                invalid.append(row["pointName"])
                continue
            else:
                prefix = "pp_"
            points.append(
                {
                    "pointName": row["pointName"],
                    "positionX": row[prefix + "x"] if prefix else row["positionX"],
                    "positionY": row[prefix + "y"] if prefix else row["positionY"],
                    "positionZ": (
                        row[prefix + "z"] if prefix else row["positionZ"]
                    )
                    or 0.0,
                    "orientationX": (
                        row[prefix + "ox"] if prefix else row["orientationX"]
                    )
                    or 0.0,
                    "orientationY": (
                        row[prefix + "oy"] if prefix else row["orientationY"]
                    )
                    or 0.0,
                    "orientationZ": (
                        row[prefix + "oz"] if prefix else row["orientationZ"]
                    )
                    or 0.0,
                    "orientationW": (
                        row[prefix + "ow"] if prefix else row["orientationW"]
                    )
                    if (
                        row[prefix + "ow"] if prefix else row["orientationW"]
                    )
                    is not None
                    else 1.0,
                    "action": _first_nonempty(
                        row["tp_action"],
                        None if row["isTemporary"] else row["pp_action"],
                    ),
                    "actionContent": _first_nonempty(
                        row["tp_action_content"],
                        None if row["isTemporary"] else row["pp_action_content"],
                    ),
                }
            )
        if invalid:
            return fail("以下点位已不存在,请先修正任务: %s" % "、".join(invalid))

    return _send_task(task["id"], task["taskName"], points)


@router.get("/nav_multi/pause", response_model=ApiResponse)
@router.post("/nav_multi/pause", response_model=ApiResponse)
def nav_pause() -> ApiResponse:
    """暂停当前导航任务。"""
    success, message = ros_client.pause_nav()
    return ok(None, message) if success else fail(message)


@router.get("/nav_multi/resume", response_model=ApiResponse)
@router.post("/nav_multi/resume", response_model=ApiResponse)
def nav_resume() -> ApiResponse:
    """仅在自动控制权下恢复暂停的导航任务。"""
    allowed, reason = navigation_allowed()
    if not allowed:
        return fail("当前控制权禁止恢复导航: %s" % reason)
    success, message = ros_client.resume_nav()
    return ok(None, message) if success else fail(message)


@router.get("/nav_multi/cancel", response_model=ApiResponse)
@router.post("/nav_multi/cancel", response_model=ApiResponse)
def nav_cancel() -> ApiResponse:
    """立即取消当前导航任务。"""
    success, message = ros_client.cancel_nav()
    return ok(None, message) if success else fail(message)


@router.get("/nav_multi/next", response_model=ApiResponse)
@router.post("/nav_multi/next", response_model=ApiResponse)
def nav_next() -> ApiResponse:
    """推进到下一站。

    调用约定的 ROS 端 `std_srvs/Trigger` 服务 `/nav_multi/next`;
    当 ROS 包尚未实现该 service 时,会失败并把错误信息透传给前端。
    """
    success, message = ros_client.next_nav_point()
    return ok(None, message) if success else fail(message)


@router.get("/nav_multi/end", response_model=ApiResponse)
@router.post("/nav_multi/end", response_model=ApiResponse)
def nav_end() -> ApiResponse:
    """结束当前导航任务。

    调用约定的 ROS 端 `std_srvs/Trigger` 服务 `/nav_multi/end`;
    当 ROS 包尚未实现该 service 时,会失败并把错误信息透传给前端。
    """
    success, message = ros_client.end_nav()
    return ok(None, message) if success else fail(message)


@router.get("/nav_multi/passage", response_model=ApiResponse)
@router.post("/nav_multi/passage", response_model=ApiResponse)
def nav_passage() -> ApiResponse:
    """通过当前关卡（放行）。

    调用约定的 ROS 端 `std_srvs/Trigger` 服务 `/nav_multi/passage`;
    当 ROS 包尚未实现该 service 时,会失败并把错误信息透传给前端。
    """
    success, message = ros_client.passage_nav()
    return ok(None, message) if success else fail(message)


@router.get("/nav_multi/status", response_model=ApiResponse)
def nav_status() -> ApiResponse:
    """获取缓存的导航任务状态。"""
    return ok(ros_client.get_nav_status())


@router.post("/nav_custom", response_model=ApiResponse)
def nav_custom(request: NavCustomRequest) -> ApiResponse:
    """导航到临时坐标或数据库中的已知点位。"""
    conflict = _check_conflict()
    if conflict:
        return fail(conflict)

    if request.pointId == -1:
        if any(
            value is None
            for value in (
                request.positionX,
                request.positionY,
                request.orientationZ,
                request.orientationW,
            )
        ):
            return fail("临时点位模式(pointId=-1)缺少坐标字段")
        point = {
            "pointName": "临时导航",
            "positionX": request.positionX,
            "positionY": request.positionY,
            "positionZ": request.positionZ,
            "orientationX": request.orientationX,
            "orientationY": request.orientationY,
            "orientationZ": request.orientationZ,
            "orientationW": request.orientationW,
            "action": "",
            "actionContent": "",
        }
    elif request.pointId > 0:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT pointName, positionX, positionY, positionZ, "
                "orientationX, orientationY, orientationZ, orientationW, "
                "action, actionContent FROM PointPosition WHERE id = ?",
                (request.pointId,),
            ).fetchone()
        if row is None:
            return fail("点位不存在: pointId=%d" % request.pointId)
        point = dict(row)
    else:
        return fail("pointId 必须为 -1 或 >0")

    return _send_task(-1, "导航到 %s" % point["pointName"], [point])
