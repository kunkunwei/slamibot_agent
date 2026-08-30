#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证激光点(base_link系)转换到 map 系是否正确(costmap obstacle_layer 的关键转换)。"""
import math
import rospy
import tf2_ros
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import PoseWithCovarianceStamped

rospy.init_node("laser_xform_test", anonymous=True)
buf = tf2_ros.Buffer()
tf2_ros.TransformListener(buf)
rospy.sleep(2.0)

scan = rospy.wait_for_message("/scan", LaserScan, timeout=8)
n = len(scan.ranges)
print("scan n=%d angle_min=%.3f angle_max=%.3f inc=%.4f" % (
    n, scan.angle_min, scan.angle_max, scan.angle_increment))
print("scan stamp=%s frame=%s" % (scan.header.stamp, scan.header.frame_id))

# 取正前方 + 左右 90 度 的 laser 点
idxs = [0, n // 4, n // 2, 3 * n // 4]  # 前, 右, 后, 左
for i in idxs:
    r = scan.ranges[i]
    a = scan.angle_min + i * scan.angle_increment
    if not math.isfinite(r) or r <= 0:
        continue
    # base_link 系激光点
    lx = r * math.cos(a)
    ly = r * math.sin(a)
    try:
        t = buf.lookup_transform("map", "base_link", scan.header.stamp)
        # 应用 map->base_link 变换(把 base_link 点转到 map)
        px, py, pz = t.transform.translation.x, t.transform.translation.y, t.transform.translation.z
        qx, qy, qz, qw = (t.transform.rotation.x, t.transform.rotation.y,
                          t.transform.rotation.z, t.transform.rotation.w)
        # 旋转 base_link 向量
        vx, vy = lx, ly
        # 四元数旋转 (仅 z 轴相关)
        s = qw * qw - qz * qz
        rx = vx * (qw * qw - qz * qz) + vy * (2 * qw * qz)  # 简化z轴旋转
        ry = vx * (-2 * qw * qz) + vy * (qw * qw - qz * qz)
        # 完整 z 轴旋转: [cos, -sin; sin, cos]
        yaw = math.atan2(2 * (qw * qz), 1 - 2 * qz * qz)
        mx = px + vx * math.cos(yaw) - vy * math.sin(yaw)
        my = py + vx * math.sin(yaw) + vy * math.cos(yaw)
        print("laser idx=%d angle=%.3f r=%.3f base(%.3f,%.3f) -> map(%.3f,%.3f)" % (
            i, a, r, lx, ly, mx, my))
    except Exception as e:
        print("idx=%d lookup fail: %s" % (i, e))

# AMCL 位姿对照
try:
    pose = rospy.wait_for_message("/amcl_pose", PoseWithCovarianceStamped, timeout=5)
    print("AMCL robot map pose=(%.3f,%.3f)" % (pose.pose.pose.position.x, pose.pose.pose.position.y))
except Exception as e:
    print("amcl fail: %s" % e)
rospy.signal_shutdown("done")
