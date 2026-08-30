#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 global costmap 中机器人位置与点位是否可规划。"""
import rospy
from nav_msgs.msg import OccupancyGrid

rospy.init_node("costmap_check", anonymous=True)
cm = rospy.wait_for_message("/move_base/global_costmap/costmap", OccupancyGrid, timeout=10)
w, h, res = cm.info.width, cm.info.height, cm.info.resolution
ox, oy = cm.info.origin.position.x, cm.info.origin.position.y
print("costmap %dx%d res=%.3f origin=(%.3f,%.3f) stamp=%s" % (w, h, res, ox, oy, cm.header.stamp.secs))

# 机器人 map 位姿(AMCL amcl_pose 值)
rx, ry = 0.063, 0.075
ix = int((rx - ox) / res)
iy = int((ry - oy) / res)
print("robot map=(%.3f,%.3f) cell=(%d,%d)" % (rx, ry, ix, iy))

if 0 <= ix < w and 0 <= iy < h:
    v = cm.data[iy * w + ix]
    print("robot_cell_val=%d (0=free, 1-99=inflated, 100=obstacle, -1=unknown)" % v)
    vals = []
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            xx, yy = ix + dx, iy + dy
            if 0 <= xx < w and 0 <= yy < h:
                vals.append(cm.data[yy * w + xx])
    print("7x7 around robot: n=%d free=%d infl(1-69)=%d obs(70+)=%d unk=%d" % (
        len(vals), sum(1 for v in vals if v == 0),
        sum(1 for v in vals if 1 <= v < 70),
        sum(1 for v in vals if v >= 70), sum(1 for v in vals if v < 0)))
else:
    print("ROBOT OUTSIDE COSTMAP!")

# 全图统计
obs = sum(1 for v in cm.data if v >= 70)
unk = sum(1 for v in cm.data if v < 0)
fr = sum(1 for v in cm.data if v == 0)
infl = sum(1 for v in cm.data if 1 <= v < 70)
print("costmap total=%d obstacle=%d inflated=%d free=%d unknown=%d" % (
    len(cm.data), obs, infl, fr, unk))

# 检查机器人 cell 是否为 obstacle(判断 AMCL 位姿是否落在障碍里)
if 0 <= ix < w and 0 <= iy < h and cm.data[iy * w + ix] >= 70:
    print("!! ROBOT IS IN OBSTACLE CELL -> 无法规划(起点在障碍内)")
rospy.signal_shutdown("done")
