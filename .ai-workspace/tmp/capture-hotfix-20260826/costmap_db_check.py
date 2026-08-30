#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""costmap 机器人位置检查 + nav_api.db 点位查询。"""
import os, sqlite3
import rospy
from nav_msgs.msg import OccupancyGrid

# --- 1) costmap ---
rospy.init_node("costmap_db_check", anonymous=True)
try:
    cm = rospy.wait_for_message("/move_base/global_costmap/costmap", OccupancyGrid, timeout=20)
    w, h, res = cm.info.width, cm.info.height, cm.info.resolution
    ox, oy = cm.info.origin.position.x, cm.info.origin.position.y
    print("costmap %dx%d res=%.3f origin=(%.3f,%.3f) stamp=%s" % (w, h, res, ox, oy, cm.header.stamp.secs))
    rx, ry = 0.063, 0.075
    ix = int((rx - ox) / res)
    iy = int((ry - oy) / res)
    print("robot map=(%.3f,%.3f) cell=(%d,%d)" % (rx, ry, ix, iy))
    if 0 <= ix < w and 0 <= iy < h:
        v = cm.data[iy * w + ix]
        print("robot_cell_val=%d (0=free, 1-69=inflated, 70+=obstacle, -1=unknown)" % v)
        vals = []
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                xx, yy = ix + dx, iy + dy
                if 0 <= xx < w and 0 <= yy < h:
                    vals.append(cm.data[yy * w + xx])
        print("7x7 around: n=%d free=%d infl=%d obs=%d unk=%d" % (
            len(vals), sum(1 for v in vals if v == 0),
            sum(1 for v in vals if 1 <= v < 70),
            sum(1 for v in vals if v >= 70), sum(1 for v in vals if v < 0)))
        if v >= 70:
            print("!! ROBOT IN OBSTACLE CELL")
    else:
        print("ROBOT OUTSIDE COSTMAP!")
    obs = sum(1 for v in cm.data if v >= 70)
    unk = sum(1 for v in cm.data if v < 0)
    fr = sum(1 for v in cm.data if v == 0)
    print("costmap total=%d obstacle=%d free=%d unknown=%d" % (len(cm.data), obs, fr, unk))
except Exception as e:
    print("COSTMAP_FAIL: %s" % e)
rospy.signal_shutdown("done")

# --- 2) DB 点位 ---
db = "/Scout_mini_navigation/install/lib/python3/dist-packages/db/nav_api.db"
if os.path.exists(db):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print("TABLES:", tables)
    for t in tables:
        if "point" in t.lower() or "nav" in t.lower():
            try:
                cur.execute("PRAGMA table_info(%s)" % t)
                cols = [c[1] for c in cur.fetchall()]
                print("TABLE %s cols=%s" % (t, cols))
                cur.execute("SELECT * FROM %s LIMIT 8" % t)
                for row in cur.fetchall():
                    print("  row:", row)
            except Exception as e:
                print("  %s query fail: %s" % (t, e))
    conn.close()
else:
    print("DB NOT FOUND:", db)
