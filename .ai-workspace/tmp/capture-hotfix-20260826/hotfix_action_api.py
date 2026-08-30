# -*- coding: utf-8 -*-
"""容器热修：补充动作管理 API (/api/action/*)。

- action.py：由调用方 scp + docker cp 上传（本脚本只做 py_compile 校验）
- models.py：尾部追加 NavigationAction*Request 6 个请求模型
- app.py：补 import action_router + include_router(action_router)
锚点唯一性校验，失败即抛错不写盘。
"""
import sys
import py_compile

BASE = "/Scout_mini_navigation/install/lib/python3/dist-packages"
M = BASE + "/fastapi_service/models.py"
A = BASE + "/fastapi_service/app.py"
AC = BASE + "/fastapi_service/action.py"

MODELS_BLOCK = """


class NavigationActionAddRequest(RequestModel):
    \"\"\"新增一个动作。``code`` 唯一,``enabled`` 默认 1。\"\"\"

    code: str = Field(min_length=1, description="动作唯一编码(机器名)")
    name: str = Field(min_length=1, description="动作中文名")
    category: str = Field(
        default="other",
        description="photo / chassis / other,用于 execute 分发",
    )
    description: Optional[str] = None
    enabled: int = Field(default=1, description="0=禁用 / 1=启用")


class NavigationActionUpdateRequest(RequestModel):
    \"\"\"部分更新动作信息;只传要改的字段。\"\"\"

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
    \"\"\"执行动作,body 字段名按 APP 契约为 ``action``。\"\"\"

    action: str = Field(
        min_length=1,
        description="动作编码(对应 NavigationAction.code)",
    )
"""

# ---------- models.py: 尾部追加动作请求模型 ----------
s = open(M, encoding="utf-8").read()
if "class NavigationActionAddRequest" in s:
    print("SKIP: models.py 已含动作模型")
elif not s.strip().endswith("pcdFilePath: Optional[str] = None"):
    raise RuntimeError("models.py 尾部锚点不匹配, 不写盘")
else:
    s += MODELS_BLOCK
    open(M, "w", encoding="utf-8").write(s)
    print("OK: models.py 追加 6 个动作请求模型")

# ---------- app.py: import + include_router ----------
a = open(A, encoding="utf-8").read()
if "from .action import router as action_router" in a:
    print("SKIP: app.py 已 import action_router")
else:
    old_imp = "from .models import fail\n"
    if a.count(old_imp) != 1:
        raise RuntimeError("app.py import 锚点匹配 %d 次(应为 1)" % a.count(old_imp))
    a = a.replace(old_imp, old_imp + "from .action import router as action_router\n", 1)

old_inc = "app.include_router(capture_router)\n"
if "app.include_router(action_router)" in a:
    print("SKIP: app.py 已 include action_router")
else:
    if a.count(old_inc) != 1:
        raise RuntimeError("app.py include 锚点匹配 %d 次(应为 1)" % a.count(old_inc))
    a = a.replace(old_inc, old_inc + "app.include_router(action_router)\n", 1)

open(A, "w", encoding="utf-8").write(a)
print("OK: app.py 已挂载 action_router")

# ---------- 校验 ----------
py_compile.compile(M, doraise=True)
py_compile.compile(A, doraise=True)
py_compile.compile(AC, doraise=True)
print("COMPILE_OK: models.py + app.py + action.py")
print("ALL_DONE")
