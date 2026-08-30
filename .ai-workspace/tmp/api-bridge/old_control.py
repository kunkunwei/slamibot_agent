"""High-level mapping/navigation mode controls."""

from fastapi import APIRouter

from .mcp_compat import MCPServer
from .models import ApiResponse, DefaultModeRequest, fail, ok
from . import process_manager


router = APIRouter(prefix="/api/control/mode", tags=["模式切换"])


def register_mcp_tools(mcp: MCPServer) -> None:
    mcp.tool(name="switch_to_mapping_mode")(change_mode_mapping)
    mcp.tool(name="switch_to_navigation_mode")(change_mode_navigation)
    mcp.tool(name="ensure_navigation_mode")(ensure_mode_navigation)
    mcp.tool(name="get_default_mode")(get_default_mode)
    mcp.tool(name="set_default_mode")(set_default_mode)


@router.get("/mapping", response_model=ApiResponse)
def change_mode_mapping() -> ApiResponse:
    """停止导航并切换至 FAST_LIO 建图模式。"""
    success, message = process_manager.switch_to_mapping()
    status = process_manager.get_status()
    return ok(status, message) if success else fail(message, status)


@router.get("/navigation", response_model=ApiResponse)
def change_mode_navigation() -> ApiResponse:
    """停止建图并切换至定位导航模式。"""
    success, message = process_manager.switch_to_navigation()
    status = process_manager.get_status()
    return ok(status, message) if success else fail(message, status)


@router.get("/navigation/ensure", response_model=ApiResponse)
def ensure_mode_navigation() -> ApiResponse:
    """幂等确保处于导航模式(启动 map_server 发布 /map 2D 栅格地图)。

    已处于导航模式时直接返回;否则自动切换。不发布 /cmd_vel,车不会移动。
    """
    success, message = process_manager.ensure_navigation()
    status = process_manager.get_status()
    return ok(status, message) if success else fail(message, status)


@router.get("/default", response_model=ApiResponse)
def get_default_mode() -> ApiResponse:
    """查询持久化的默认启动模式(idle / mapping / navigation)。"""
    return ok({"default_mode": process_manager.get_default_mode()})


@router.post("/default", response_model=ApiResponse)
def set_default_mode(req: DefaultModeRequest) -> ApiResponse:
    """设置默认启动模式;容器重启后自动恢复,当前状态不立即切换。"""
    success, message = process_manager.set_default_mode(req.mode)
    if success:
        return ok({"default_mode": req.mode}, message)
    return fail(message)
