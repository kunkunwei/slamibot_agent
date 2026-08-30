#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模拟 AMCL amcl_node.cpp laserReceived 里的 TF 计算,验证 transform 是否失败。

复现对象: amcl_node.cpp line 1455-1476
  构造 base_link 系 PoseStamped(stamp=最新 /scan stamp, pose=AMCL 估计位姿),
  调 tf_buffer.transform(ps, "odom")。
若失败 -> 复现了 map->odom TF 不发布的原因。
"""
import rospy
import tf2_ros
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import LaserScan

rospy.init_node("amcl_tf_sim", anonymous=True)
tf_buffer = tf2_ros.Buffer()
tf2_ros.TransformListener(tf_buffer)
rospy.sleep(2.0)

scan = rospy.wait_for_message("/scan", LaserScan, timeout=8)
print("SCAN stamp=%s secs=%s frame=%s" % (
    scan.header.stamp, scan.header.stamp.secs, scan.header.frame_id))
print("SCAN now=%s" % rospy.Time.now())

# 1) 模拟 line 1455-1476: base_link 系位姿 -> odom
ps = PoseStamped()
ps.header.frame_id = "base_link"
ps.header.stamp = scan.header.stamp
ps.pose.position.x = 0.06316563179243806
ps.pose.position.y = 0.07529299108722122
ps.pose.orientation.w = 1.0
try:
    out = tf_buffer.transform(ps, "odom")
    print("TRANSFORM_OK -> odom pose x=%.3f y=%.3f yaw=%.3f" % (
        out.pose.position.x, out.pose.position.y,
        2 * __import__("math").atan2(out.pose.orientation.z, out.pose.orientation.w)))
except Exception as e:
    print("TRANSFORM_FAIL: %s" % e)

# 2) 检查 laser frame 的 TF (frame_to_laser 是否可用)
try:
    t = tf_buffer.lookup_transform("base_link", scan.header.frame_id, scan.header.stamp)
    print("LASER_TF_OK %s->base_link x=%.3f y=%.3f" % (
        scan.header.frame_id, t.transform.translation.x, t.transform.translation.y))
except Exception as e:
    print("LASER_TF_FAIL: %s" % e)

# 3) 检查 odom->base_link 在 scan stamp 时刻
try:
    t = tf_buffer.lookup_transform("odom", "base_link", scan.header.stamp)
    print("ODOM_TF_OK odom->base_link x=%.3f y=%.3f" % (
        t.transform.translation.x, t.transform.translation.y))
except Exception as e:
    print("ODOM_TF_FAIL: %s" % e)

# 4) 检查 map frame 是否存在
try:
    t = tf_buffer.lookup_transform("map", "base_link", rospy.Time())
    print("MAP_TF_OK map->base_link x=%.3f y=%.3f" % (
        t.transform.translation.x, t.transform.translation.y))
except Exception as e:
    print("MAP_TF_FAIL: %s" % e)

rospy.signal_shutdown("done")
