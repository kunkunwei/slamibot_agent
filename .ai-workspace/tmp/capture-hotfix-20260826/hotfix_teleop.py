# -*- coding: utf-8 -*-
"""容器热修：手动遥控速度上限 0.5 -> 1.5（仅两行常量）。"""
import sys

P = "/Scout_mini_navigation/install/lib/python3/dist-packages/fastapi_service/teleop.py"

s = open(P, encoding="utf-8").read()

repls = [
    ("DEFAULT_MAX_LINEAR = 0.5", "DEFAULT_MAX_LINEAR = 1.5"),
    ("DEFAULT_MAX_ANGULAR = 0.5", "DEFAULT_MAX_ANGULAR = 1.5"),
]
for old, new in repls:
    count = s.count(old)
    if count != 1:
        raise RuntimeError("锚点匹配 %d 次(应为 1): %r" % (count, old))
    s = s.replace(old, new, 1)

open(P, "w", encoding="utf-8").write(s)
print("OK: teleop.py 速度上限已改为 1.5")
print("ALL_DONE")
