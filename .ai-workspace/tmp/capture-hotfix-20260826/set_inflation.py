#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行时修改 costmap inflation 参数（不重启 move_base）。
global/local 统一为 0.06 + 12.0（与 costmap_common / tuned2 注释意图一致）。"""
import rospy
from dynamic_reconfigure.srv import Reconfigure, ReconfigureRequest
from dynamic_reconfigure.msg import Config, DoubleParameter

rospy.init_node("set_inflation", anonymous=True)
targets = [
    ("/move_base/global_costmap/inflation", 0.06, 12.0),
    ("/move_base/local_costmap/inflation", 0.06, 12.0),
]
for ns, radius, scale in targets:
    svc = ns + "/set_parameters"
    try:
        rospy.wait_for_service(svc, timeout=8)
        client = rospy.ServiceProxy(svc, Reconfigure)
        cfg = Config()
        cfg.doubles = [
            DoubleParameter("inflation_radius", radius),
            DoubleParameter("cost_scaling_factor", scale),
        ]
        resp = client(ReconfigureRequest(config=cfg))
        print("SET OK %s -> inflation_radius=%.3f cost_scaling_factor=%.1f" % (ns, radius, scale))
    except Exception as e:
        print("FAIL %s : %s" % (svc, e))
rospy.signal_shutdown("done")
