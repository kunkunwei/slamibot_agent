"""静态验证:逐模块 import router,遍历 router.routes 确认补全的 API 已注册。

注意:本容器 FastAPI 为魔改版,include_router 生成懒加载 _IncludedRouter,
app.routes 不展开子路由,故直接遍历各模块 router.routes 验证。
"""
import sys

sys.path.insert(0, "/Scout_mini_navigation/install/lib/python3/dist-packages")
sys.path.insert(0, "/Scout_mini_navigation")

import fastapi_service
print("FASTAPI_SERVICE_MODULE=%s" % fastapi_service.__file__)

MODULES = [
    "fastapi_service.base_mode",
    "fastapi_service.action",
    "fastapi_service.control",
    "fastapi_service.map_api",
    "fastapi_service.point",
    "fastapi_service.task",
    "fastapi_service.launch_api",
    "fastapi_service.process_manager",
]

for mod_name in MODULES:
    mod = __import__(mod_name, fromlist=["router"])
    router = getattr(mod, "router", None)
    if router is None:
        print("\n### %s: NO router attribute" % mod_name)
        continue
    routes = getattr(router, "routes", [])
    print("\n### %s : %d routes" % (mod_name, len(routes)))
    for r in routes:
        methods = sorted(getattr(r, "methods", None) or [])
        path = getattr(r, "path", "")
        print("   %-8s %-55s" % (",".join(methods), path))

print("\n=== process_manager 导出函数检查 ===")
from fastapi_service import process_manager as pm
missing = [f for f in [
    "ensure_navigation", "get_default_mode", "get_status", "restore_default_mode",
    "set_default_mode", "start_mapping", "start_navigation", "start_pcd",
    "stop_mapping", "stop_navigation", "switch_to_mapping", "switch_to_navigation",
] if not hasattr(pm, f)]
print("process_manager missing:", missing if missing else "NONE (all 12 present)")

print("\nverify_routes DONE")
