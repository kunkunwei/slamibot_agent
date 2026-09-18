"""ASGI entry point for the incremental FastAPI + MCP migration."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import dog, process_manager
from .assistant import assistant_service, router as assistant_router
from .database import init_db
from .mcp_compat import MCPServer
from .models import fail
from .area import register_mcp_tools as register_area_tools
from .area import router as area_router
from .capture import CAPTURE_DIR
from .capture import camera_router
from .capture import register_mcp_tools as register_capture_tools
from .capture import router as capture_router
from .control import register_mcp_tools as register_control_tools
from .control import router as control_router
from .launch_api import register_mcp_tools as register_launch_tools
from .launch_api import router as launch_router
from .localization import register_mcp_tools as register_localization_tools
from .localization import router as localization_router
from .map_api import register_mcp_tools as register_map_tools
from .map_api import router as map_router
from .navigation import register_mcp_tools as register_navigation_tools
from .navigation import router as navigation_router
from .point import register_mcp_tools, router as point_router
from .point_arrival import point_arrival_dispatcher
from .ros_client import ros_client
from .status import register_mcp_tools as register_status_tools
from .status import router as status_router
from .task import register_mcp_tools as register_task_tools
from .task import router as task_router
from .teleop import register_mcp_tools as register_teleop_tools
from .teleop import router as teleop_router
from .teleop import teleop_controller
from .voice import register_mcp_tools as register_voice_tools
from .voice import router as voice_router
from .audio import router as audio_router
from .base_mode import router as base_mode_router
from .base_mode import base_mode_manager
from .action import router as action_router


mcp = MCPServer(
    "scout-navigation",
    instructions="Scout Mini 地图、点位与导航控制工具。",
)
register_mcp_tools(mcp)
register_task_tools(mcp)
register_localization_tools(mcp)
register_navigation_tools(mcp)
register_map_tools(mcp)
register_control_tools(mcp)
register_launch_tools(mcp)
register_status_tools(mcp)
register_area_tools(mcp)
register_teleop_tools(mcp)
register_capture_tools(mcp)
mcp_http_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    # 恢复持久化的默认启动模式:容器/FastAPI 重启后自动进入默认模式,
    # 让 /map 2D 栅格地图无需手动切换导航模式即可出现。
    # 非致命:启动初期 ROS 时间(/clock)未就绪时 switch 会 fail-fast,
    # 失败仅打日志,由容器自检守护(nav-healthcheck.sh)周期兜底。
    try:
        mode_ok, mode_msg = process_manager.restore_default_mode()
        if not mode_ok:
            logging.warning("lifespan: 恢复默认模式失败: %s", mode_msg)
    except Exception as exc:
        logging.warning("lifespan: 恢复默认模式异常: %s", exc)
    point_arrival_dispatcher.start()
    ros_client.start()
    ros_client.start_camera_cache()
    # 非致命地启动 PCD 发布器:让前端一进入导航模式即可看到点云,
    # 而无需先点击建图再点导航。失败仅打日志,不阻断 API 启动。
    try:
        pcd_ok, pcd_msg = process_manager.start_pcd()
        if not pcd_ok:
            logging.warning("lifespan: PCD 发布器未启动: %s", pcd_msg)
    except Exception as exc:
        logging.warning("lifespan: 启动 PCD 发布器异常: %s", exc)
    try:
        # 注册 APP 摇杆安全控制链路;失败仅记录日志,不阻断 API。
        teleop_controller.attach()
    except Exception as exc:
        logging.warning("lifespan: 启动 teleop 异常: %s", exc)
    try:
        async with mcp.session_manager.run():
            yield
    finally:
        try:
            assistant_service.stop()
        except Exception as exc:
            logging.warning("lifespan: 停止 assistant worker 异常: %s", exc)
        # 先停止机器狗动作入口，确保退出阶段立即发出 StopMove 并清理连接。
        try:
            dog.shutdown()
        except Exception as exc:
            logging.warning("lifespan: 停止 dog driver 异常: %s", exc)
        # 再注销到点 handler 并停止动作 worker,避免清理阶段继续接收副作用。
        try:
            point_arrival_dispatcher.stop()
        except Exception as exc:
            logging.warning("lifespan: 停止 point_arrival 异常: %s", exc)
        # 退出阶段:即便 mcp session 或 yield 内抛异常,也要非致命地清理
        # PCD、teleop 与 ros_client;三者相互独立,任一异常都不能阻断另一个清理动作。
        try:
            base_mode_manager.shutdown()
        except Exception as exc:
            logging.warning("lifespan: 停止 base_mode 异常: %s", exc)
        try:
            teleop_controller.shutdown()
        except Exception as exc:
            logging.warning("lifespan: 停止 teleop 异常: %s", exc)
        try:
            process_manager.stop_pcd()
        except Exception as exc:
            logging.warning("lifespan: 停止 PCD 发布器异常: %s", exc)
        try:
            ros_client.stop()
        except Exception as exc:
            logging.warning("lifespan: 停止 ros_client 异常: %s", exc)


app = FastAPI(
    title="Scout Mini Navigation API",
    description="FastAPI + MCP 渐进迁移服务。",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = [
    origin.strip()
    for origin in os.environ.get("NAV_API_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request, exc: RequestValidationError
) -> JSONResponse:
    fields = [".".join(str(part) for part in error["loc"][1:]) for error in exc.errors()]
    response = fail("请求参数校验失败: %s" % ", ".join(fields))
    return JSONResponse(status_code=200, content=response.model_dump())


@app.get("/health", tags=["系统"])
def health() -> dict:
    return {
        "success": True,
        "service": "nav-api-fastapi",
        "rosbridgeConnected": ros_client.is_connected,
    }


app.include_router(point_router)
app.include_router(task_router)
app.include_router(localization_router)
app.include_router(navigation_router)
app.include_router(map_router)
app.include_router(control_router)
app.include_router(launch_router)
app.include_router(status_router)
app.include_router(assistant_router)
app.include_router(voice_router)
app.include_router(audio_router)
app.include_router(area_router)
app.include_router(teleop_router)
app.include_router(base_mode_router)
app.include_router(action_router)
app.include_router(capture_router)
app.include_router(camera_router)

# 照片静态回读必须位于 MCP 根路径兜底挂载之前。
app.mount(
    "/captures",
    StaticFiles(directory=CAPTURE_DIR, check_dir=False),
    name="captures",
)


# Keep this last: Mount("/") is a catch-all route. The MCP endpoint is /mcp.
app.mount("/", mcp_http_app)
