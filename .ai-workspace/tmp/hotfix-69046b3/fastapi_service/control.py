"""High-level mapping/navigation mode controls."""

from fastapi import APIRouter

from .mcp_compat import MCPServer
from .models import ApiResponse, DefaultModeRequest, fail, ok
from . import process_manager
from .control_ownership import OWNER_AUTO, claim, snapshot
from .mode_coordinator import force_manual_takeover, force_mapping_mode


router = APIRouter(prefix="/api/control/mode", tags=["模式切换"])


def register_mcp_tools(mcp: MCPServer) -> None:
    mcp.tool(name="switch_to_mapping_mode")(change_mode_mapping)
    mcp.tool(name="force_manual_takeover")(change_mode_manual_force)
    mcp.tool(name="switch_to_navigation_mode")(change_mode_navigation)
    mcp.tool(name="ensure_navigation_mode")(ensure_mode_navigation)
    mcp.tool(name="get_default_mode")(get_default_mode)
    mcp.tool(name="set_default_mode")(set_default_mode)


@router.api_route("/mapping", methods=["GET", "POST"], response_model=ApiResponse)
@router.post("/mapping/force", response_model=ApiResponse)
def change_mode_mapping() -> ApiResponse:
    """强制停止运动与导航，并切换至 FAST_LIO 建图模式。"""
    return force_mapping_mode()


@router.post("/manual/force", response_model=ApiResponse)
def change_mode_manual_force() -> ApiResponse:
    """卡死或失败时仍尽最大努力停止导航并启用手动遥控。"""
    return force_manual_takeover()


@router.get("/navigation", response_model=ApiResponse)
def change_mode_navigation() -> ApiResponse:
    """停止建图并切换至定位导航模式。"""
    previous_owner = snapshot()["owner"]
    success, message = process_manager.switch_to_navigation()
    status = process_manager.get_status()
    if success:
        claim(OWNER_AUTO)
        return ok(status, message)
    # A failed switch must not silently release a manual/mapping safety latch.
    return fail(message, {**status, "controlOwner": previous_owner})


@router.get("/navigation/ensure", response_model=ApiResponse)
def ensure_mode_navigation() -> ApiResponse:
    """安全确保导航模式；建图或模式切换期间返回 MAPPING_ACTIVE。

    该入口 fail-closed，绝不会为了确保导航而停止正在进行的建图。
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
