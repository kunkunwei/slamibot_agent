#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读 /map 与 global costmap, 检查机器人位置 cell 与障碍分布。"""
import rospy
from nav_msgs.msg import OccupancyGrid

rospy.init_node("map_check", anonymous=True)

def check(grid, label, rx, ry):
    w, h, res = grid.info.width, grid.info.height, grid.info.resolution
    ox, oy = grid.info.origin.position.x, grid.info.origin.position.y
    ix = int((rx - ox) / res)
    iy = int((ry - oy) / res)
    obs = sum(1 for v in grid.data if v >= 70)
    unk = sum(1 for v in grid.data if v < 0)
    fr = sum(1 for v in grid.data if v == 0)
    print("%s: %dx%d res=%.3f origin=(%.2f,%.2f) total=%d obs=%d free=%d unk=%d" % (
        label, w, h, res, ox, oy, len(grid.data), obs, fr, unk))
    if 0 <= ix < w and 0 <= iy < h:
        v = grid.data[iy * w + ix]
        vals = []
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                xx, yy = ix + dx, iy + dy
                if 0 <= xx < w and 0 <= yy < h:
                    vals.append(grid.data[yy * w + xx])
        print("  robot(%.2f,%.2f) cell=(%d,%d) val=%d | 7x7: free=%d infl=%d obs=%d unk=%d" % (
            rx, ry, ix, iy, v,
            sum(1 for x in vals if x == 0), sum(1 for x in vals if 1 <= x < 70),
            sum(1 for x in vals if x >= 70), sum(1 for x in vals if x < 0)))
    else:
        print("  robot OUTSIDE grid!")

# AMCL 位姿
from geometry_msgs.msg import PoseWithCovarianceStamped
try:
    pose = rospy.wait_for_message("/amcl_pose", PoseWithCovarianceStamped, timeout=5)
    rx, ry = pose.pose.pose.position.x, pose.pose.pose.position.y
    print("AMCL pose=(%.3f,%.3f)" % (rx, ry))
except Exception as e:
    rx, ry = 0.08, 0.06
    print("amcl_pose fail: %s" % e)

# 1) /map
try:
    grid = rospy.wait_for_message("/map", OccupancyGrid, timeout=6)
    check(grid, "MAP", rx, ry)
except Exception as e:
    print("MAP fail: %s" % e)

# 2) global costmap (等待较久)
try:
    grid = rospy.wait_for_message("/move_base/global_costmap/costmap", OccupancyGrid, timeout=35)
    check(grid, "GLOBAL_COSTMAP", rx, ry)
except Exception as e:
    print("GLOBAL_COSTMAP fail: %s" % e)

rospy.signal_shutdown("done")
