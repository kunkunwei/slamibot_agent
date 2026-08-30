#!/usr/bin/env python3
# best_match_3d.py — 3D 点云(带倾斜 TF) vs 2D 占位格 暴力匹配求真位姿
#
# 背景：MID360 倾斜 ~20° 安装，/scan 是倾斜点云压平的畸变 2D 扫描，
#       AMCL/2D 匹配被畸变骗到错位姿。本脚本直接用 livox_frame 原始 3D
#       点云，经 base_link<-livox_frame(含倾斜) + 候选位姿变换后投到 /map
#       占位格打分，不受 2D 投影畸变影响。
#
# 用法（板子上）:
#   source /opt/ros/noetic/setup.bash
#   python3 best_match_3d.py
#
# 只读：只订阅 /map /livox/lidar/pointcloud，不发布任何东西。
import rospy, math, time
import numpy as np
import tf
import sensor_msgs.point_cloud2 as pc2
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import OccupancyGrid

grid = None
cloud_raw = []            # 原始 livox_frame 点列表
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
    a = np.asarray(pts, dtype=np.float64)        # livox_frame
    cloud_raw.append(a)
    if len(cloud_raw) > MAX_FRAMES:
        cloud_raw.pop(0)

def main():
    global grid, cloud_raw
    rospy.init_node('best_match_3d', anonymous=True)
    rospy.Subscriber('/map', OccupancyGrid, map_cb, queue_size=1)
    sub = rospy.Subscriber('/livox/lidar/pointcloud', PointCloud2,
                           cloud_cb, queue_size=10, buff_size=2**24)
    listener = tf.TransformListener()

    # 取 TF base_link <- livox_frame（静态，含倾斜）
    t0 = time.time()
    trans = rot = None
    while not rospy.is_shutdown() and time.time() - t0 < 15:
        try:
            (trans, rot) = listener.lookupTransform('base_link', 'livox_frame', rospy.Time(0))
            break
        except Exception:
            rospy.sleep(0.25)
    if trans is None:
        rospy.logerr("取不到 TF base_link<-livox_frame，退出"); return
    R_lb = tf.transformations.quaternion_matrix(rot)[:3, :3]
    T_lb = np.array(trans, dtype=np.float64)
    rospy.loginfo("TF livox->base: t=%s", T_lb)

    # 采集 map + 点云
    while not rospy.is_shutdown() and time.time() - t0 < 25:
        if grid is not None and cloud_raw:
            break
        rospy.sleep(0.3)
    if grid is None:
        rospy.logerr("没等到 /map"); return
    if not cloud_raw:
        rospy.logerr("没等到点云"); return
    rospy.loginfo("采集到 %d 帧点云", len(cloud_raw))
    sub.unregister()

    # 变换到 base_link 并做高度带过滤（避开地板/天花板）
    pts = []
    for a in cloud_raw:
        p = a @ R_lb.T + T_lb                      # livox_frame -> base_link
        mask = (p[:, 2] >= 0.05) & (p[:, 2] <= 1.8)
        pts.append(p[mask])
    pts = np.vstack(pts)
    rospy.loginfo("过滤后点数: %d", len(pts))

    # 占位格
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
        valid = (ix >= 0) & (ix < grid.info.width) & (iy >= 0) & (iy < grid.info.height)
        if not valid.any():
            return 0.0, 0, 0
        v = occ[iy[valid], ix[valid]]
        hits = int((v > 50).sum())
        return hits / valid.sum(), hits, int(valid.sum())

    # ---- 粗搜索 ----
    xg = np.arange(-3.5, 4.0, 0.3)
    yg = np.arange(-3.5, 4.0, 0.3)
    yawg = np.arange(0, 2 * math.pi, math.radians(15))
    best = (0.0, 0, 0, 0.0, 0.0, 0.0)
    n = len(xg) * len(yg) * len(yawg)
    done = 0
    for x in xg:
        for y in yg:
            for yaw in yawg:
                s = score(x, y, yaw)
                if s[0] > best[0]:
                    best = (s[0], s[1], s[2], x, y, yaw)
                    rospy.loginfo("  新最优 %.3f hits=%d/%d pose=(%.2f, %.2f, %.0f°)",
                                  best[0], best[1], best[2], best[3], best[4], math.degrees(best[5]))
                done += 1
    rospy.loginfo("粗搜索完成 %d 个候选. BEST=%.3f hits=%d/%d (%.2f, %.2f, %.1f°)",
                  n, best[0], best[1], best[2], best[3], best[4], math.degrees(best[5]))

    # ---- 精搜索（围绕粗最优） ----
    bx, by, byaw = best[3], best[4], best[5]
    best2 = best
    for dx in np.arange(-0.25, 0.30, 0.05):
        for dy in np.arange(-0.25, 0.30, 0.05):
            for dyaw in np.arange(-0.12, 0.15, 0.04):
                s = score(bx + dx, by + dy, byaw + dyaw)
                if s[0] > best2[0]:
                    best2 = (s[0], s[1], s[2], bx + dx, by + dy, byaw + dyaw)
    rospy.loginfo("精搜索完成. BEST=%.3f hits=%d/%d pose=(%.2f, %.2f, %.1f°)",
                  best2[0], best2[1], best2[2], best2[3], best2[4], math.degrees(best2[5]))
    print("RESULT %.3f %.3f %.3f %.1f" % (best2[0], best2[3], best2[4], math.degrees(best2[5])))

if __name__ == '__main__':
    main()
