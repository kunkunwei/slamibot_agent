#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用 move_base GlobalPlanner/make_plan, 验证全局规划是否可行(完全只读, 不动车)。"""
import rospy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.srv import GetPlan

rospy.init_node("plan_test", anonymous=True)

# 起点 = 当前 AMCL 位姿
try:
    pose = rospy.wait_for_message("/amcl_pose", PoseWithCovarianceStamped, timeout=6)
    sx, sy = pose.pose.pose.position.x, pose.pose.pose.position.y
    cov = pose.pose.covariance
    print("AMCL pose=(%.3f,%.3f) cov_xx=%.3f cov_yy=%.3f" % (sx, sy, cov[0], cov[7]))
except Exception as e:
    sx, sy = 0.08, 0.06
    print("amcl_pose read fail: %s (use default)" % e)

rospy.wait_for_service("/move_base/GlobalPlanner/make_plan", timeout=8)
planner = rospy.ServiceProxy("/move_base/GlobalPlanner/make_plan", GetPlan)

def mk_pose(x, y):
    p = PoseStamped()
    p.header.frame_id = "map"
    p.header.stamp = rospy.Time(0)
    p.pose.position.x = x
    p.pose.position.y = y
    p.pose.orientation.w = 1.0
    return p

start = mk_pose(sx, sy)
for name, gx, gy in [("point1(1.448,3.206)", 1.448, 3.206), ("near(0.5,0.5)", 0.5, 0.5)]:
    try:
        resp = planner(start, mk_pose(gx, gy), 0.1)
        n = len(resp.plan.poses)
        if n:
            last = resp.plan.poses[-1]
            print("PLAN %s: OK %d poses, last=(%.2f,%.2f)" % (name, n, last.pose.position.x, last.pose.position.y))
        else:
            print("PLAN %s: EMPTY -> 规划失败" % name)
    except Exception as e:
        print("PLAN %s FAIL: %s" % (name, e))

rospy.signal_shutdown("done")
