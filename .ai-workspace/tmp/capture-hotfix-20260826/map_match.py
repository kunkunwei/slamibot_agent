#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 AMCL 位姿: 把 laser 点转换到 map 后, 检查是否与地图障碍匹配。
若大量 laser 点落在 map free 区 -> AMCL 位姿可能错误。"""
import math
import rospy
import tf2_ros
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseWithCovarianceStamped

rospy.init_node("map_match", anonymous=True)
buf = tf2_ros.Buffer()
tf2_ros.TransformListener(buf)
rospy.sleep(2.0)

grid = rospy.wait_for_message("/map", OccupancyGrid, timeout=8)
w, h, res = grid.info.width, grid.info.height, grid.info.resolution
ox, oy = grid.info.origin.position.x, grid.info.origin.position.y
print("map %dx%d res=%.3f origin=(%.2f,%.2f)" % (w, h, res, ox, oy))

def cell_val(x, y):
    ix = int((x - ox) / res)
    iy = int((y - oy) / res)
    if 0 <= ix < w and 0 <= iy < h:
        return grid.data[iy * w + ix]
    return None

scan = rospy.wait_for_message("/scan", LaserScan, timeout=8)
t = buf.lookup_transform("map", "base_link", scan.header.stamp)
px, py = t.transform.translation.x, t.transform.translation.y
qz, qw = t.transform.rotation.z, t.transform.rotation.w
yaw = math.atan2(2 * (qw * qz), 1 - 2 * qz * qz)
print("map->base_link = (%.3f,%.3f) yaw=%.3f" % (px, py, yaw))

hit_obs = miss_free = near = total = 0
rows = []
for i in range(0, len(scan.ranges), 4):  # 采样 1/4
    r = scan.ranges[i]
    if not math.isfinite(r) or r <= 0 or r > 10:
        continue
    a = scan.angle_min + i * scan.angle_increment
    lx, ly = r * math.cos(a), r * math.sin(a)
    mx = px + lx * math.cos(yaw) - ly * math.sin(yaw)
    my = py + lx * math.sin(yaw) + ly * math.cos(yaw)
    v = cell_val(mx, my)
    if v is None:
        continue
    total += 1
    if v >= 70:
        hit_obs += 1
        rows.append((i, r, v, "OBS"))
    elif v == 0:
        miss_free += 1
        rows.append((i, r, v, "FREE"))
    elif 0 < v < 70:
        near += 1
        rows.append((i, r, v, "INFL"))

print("total=%d  hit_obs(map obs)=%d  miss_free(map free)=%d  infl=%d" % (
    total, hit_obs, miss_free, near))
print("map 障碍命中率=%.1f%%, 落空(free)率=%.1f%%" % (
    100.0 * hit_obs / total if total else 0, 100.0 * miss_free / total if total else 0))

# 打印落空的点(前15个)
print("--- miss_free 采样 ---")
mf = [r for r in rows if r[3] == "FREE"][:15]
for i, rr, v, tag in mf:
    print("  idx=%d r=%.2f map_cell=%d" % (i, rr, v))

# AMCL 位姿
try:
    pose = rospy.wait_for_message("/amcl_pose", PoseWithCovarianceStamped, timeout=5)
    print("AMCL=(%.3f,%.3f) cov_xx=%.3f" % (
        pose.pose.pose.position.x, pose.pose.pose.position.y, pose.pose.covariance[0]))
except Exception as e:
    print("amcl fail: %s" % e)
rospy.signal_shutdown("done")
