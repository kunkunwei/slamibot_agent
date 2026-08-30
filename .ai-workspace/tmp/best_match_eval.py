#!/usr/bin/env python3
# best_match_eval.py — 评估实时点云(带倾斜)在新图上的对齐度 + 局部暴力搜索真位姿
#
# 1) 用当前 TF(map<-base_link, 即 AMCL 位姿) 把实时云投到 /map 打分
# 2) 围绕该位姿做局部粗搜索 + 精搜索，找出更优位姿
#
# 只读：只订阅 /map /livox/lidar/pointcloud，不发布任何东西。
import rospy, math, time
import numpy as np
import tf
import sensor_msgs.point_cloud2 as pc2
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import OccupancyGrid

grid = None
cloud_raw = []
MAX_PTS = 40000
MAX_FRAMES = 8

def map_cb(msg):
    global grid
    if grid is None:
        grid = msg
        rospy.loginfo("map: %dx%d res=%.3f origin=(%.3f,%.3f)",
                      msg.info.width, msg.info.height, msg.info.resolution,
                      msg.info.origin.position.x, msg.info.origin.position.y)

def cloud_cb(msg):
    global cloud_raw
    if grid is None:
        return
    pts = list(pc2.read_points(msg, field_names=('x', 'y', 'z'), skip_nans=True))
    if not pts:
        return
    if len(pts) > MAX_PTS:
        step = (len(pts) // MAX_PTS) + 1
        pts = pts[::step]
    cloud_raw.append(np.asarray(pts, dtype=np.float64))
    if len(cloud_raw) > MAX_FRAMES:
        cloud_raw.pop(0)

def main():
    global grid, cloud_raw
    rospy.init_node('best_match_eval', anonymous=True)
    rospy.Subscriber('/map', OccupancyGrid, map_cb, queue_size=1)
    sub = rospy.Subscriber('/livox/lidar/pointcloud', PointCloud2,
                           cloud_cb, queue_size=10, buff_size=2**24)
    listener = tf.TransformListener()

    t0 = time.time()
    T_lb = R_lb = None
    while not rospy.is_shutdown() and time.time() - t0 < 15:
        try:
            (tr, rot) = listener.lookupTransform('base_link', 'livox_frame', rospy.Time(0))
            T_lb = np.array(tr, dtype=np.float64)
            R_lb = tf.transformations.quaternion_matrix(rot)[:3, :3]
            break
        except Exception:
            rospy.sleep(0.25)
    # 当前 AMCL 位姿（map<-base_link）
    cur_pose = None
    while not rospy.is_shutdown() and time.time() - t0 < 15:
        try:
            (tr, rot) = listener.lookupTransform('map', 'base_link', rospy.Time(0))
            yaw = math.atan2(2*(rot[3]*rot[2] + rot[0]*rot[1]), 1 - 2*(rot[1]**2 + rot[2]**2))
            cur_pose = (tr[0], tr[1], yaw)
            break
        except Exception:
            rospy.sleep(0.25)
    if cur_pose is None:
        rospy.logerr("取不到位姿 TF"); return
    rospy.loginfo("当前 AMCL 位姿: (%.3f, %.3f, %.1f°)", cur_pose[0], cur_pose[1], math.degrees(cur_pose[2]))

    while not rospy.is_shutdown() and time.time() - t0 < 25:
        if grid is not None and cloud_raw:
            break
        rospy.sleep(0.3)
    if grid is None or not cloud_raw:
        rospy.logerr("数据不足"); return
    sub.unregister()

    pts = []
    for a in cloud_raw:
        p = a @ R_lb.T + T_lb
        m = (p[:, 2] >= 0.05) & (p[:, 2] <= 1.8)
        pts.append(p[m])
    pts = np.vstack(pts)
    rospy.loginfo("过滤后点数: %d", len(pts))

    occ = np.array(grid.data, dtype=np.int8).reshape(grid.info.height, grid.info.width)
    res = float(grid.info.resolution)
    ox = float(grid.info.origin.position.x)
    oy = float(grid.info.origin.position.y)

    def score(x, y, yaw):
        c, s = math.cos(yaw), math.sin(yaw)
        px = c * pts[:, 0] - s * pts[:, 1] + x
        py = s * pts[:, 0] + c * pts[:, 1] + y
        ix = ((px - ox) / res).astype(np.int64)
        iy = ((py - oy) / res).astype(np.int64)
        v = (ix >= 0) & (ix < grid.info.width) & (iy >= 0) & (iy < grid.info.height)
        if not v.any():
            return 0.0, 0, 0
        occv = occ[iy[v], ix[v]]
        hits = int((occv > 50).sum())
        return hits / v.sum(), hits, int(v.sum())

    cx, cy, cyaw = cur_pose
    # 当前 AMCL 位姿的对齐度
    s0 = score(cx, cy, cyaw)
    rospy.loginfo(">>> 当前 AMCL 位姿对齐度: %.3f hits=%d/%d", s0[0], s0[1], s0[2])

    # 局部粗搜索（围绕 AMCL 位姿 ±3m / ±90°）
    best = s0 + (cx, cy, cyaw)
    for x in np.arange(cx - 3.0, cx + 3.01, 0.3):
        for y in np.arange(cy - 3.0, cy + 3.01, 0.3):
            for yaw in np.arange(cyaw - math.radians(90), cyaw + math.radians(91), math.radians(15)):
                s = score(x, y, yaw)
                if s[0] > best[0]:
                    best = s[0:3] + (x, y, yaw)
                    rospy.loginfo("  新最优 %.3f hits=%d/%d (%.2f, %.2f, %.0f°)",
                                  best[0], best[1], best[2], best[3], best[4], math.degrees(best[5]))
    rospy.loginfo("局部粗搜索 BEST=%.3f (%.2f, %.2f, %.1f°)", best[0], best[3], best[4], math.degrees(best[5]))

    bx, by, byaw = best[3], best[4], best[5]
    best2 = best
    for dx in np.arange(-0.25, 0.30, 0.05):
        for dy in np.arange(-0.25, 0.30, 0.05):
            for dyaw in np.arange(-0.12, 0.15, 0.04):
                s = score(bx + dx, by + dy, byaw + dyaw)
                if s[0] > best2[0]:
                    best2 = s[0:3] + (bx + dx, by + dy, byaw + dyaw)
    rospy.loginfo("精搜索 BEST=%.3f (%.2f, %.2f, %.1f°)", best2[0], best2[3], best2[4], math.degrees(best2[5]))
    rospy.loginfo("对比: 当前AMCL=%.3f, 最优=%.3f", s0[0], best2[0])
    print("EVAL current=%.3f (%.3f,%.3f,%.1f) best=%.3f (%.3f,%.3f,%.1f)" %
          (s0[0], cx, cy, math.degrees(cyaw), best2[0], best2[3], best2[4], math.degrees(best2[5])))

if __name__ == '__main__':
    main()
