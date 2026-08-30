#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多点导航编排节点 (NavMulti)。

独立于 FastAPI/MCP 进程单独运行,通过 ROS Service/Topic 与 FastAPI/MCP(nav_api)通信。

职责:
  - 接受任务(点位列表),依次调 move_base 导航到每个点位
  - 支持 暂停 / 恢复 / 取消
  - 持续发布当前状态到 /nav_multi/status (JSON over std_msgs/String)

启动方式(source devel/setup.bash 之后):
    rosrun nav_api nav_multi_node.py
"""
import json
import os
import threading

import rospy
import actionlib
from actionlib_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from std_msgs.msg import String
from std_srvs.srv import Trigger, TriggerResponse

from nav_api.srv import NavCommand, NavCommandResponse


# ============================================================
# 状态常量
# ============================================================
STATE_IDLE      = "IDLE"        # 空闲,无任务
STATE_RUNNING   = "RUNNING"     # 正在导航
STATE_PAUSED    = "PAUSED"      # 已暂停(等待 resume)
STATE_COMPLETED = "COMPLETED"   # 全部点位到达
STATE_FAILED    = "FAILED"      # 导航失败


# ============================================================
# 全局状态(由 _state_lock 保护)
# ============================================================
_state_lock     = threading.Lock()
_state          = STATE_IDLE
_task_id        = None          # 当前任务 ID
_task_name      = ""            # 当前任务名
_task_points    = []            # 点位列表 [{pointName, positionX, positionY, orientationZ, orientationW, ...}]
_current_index  = 0             # 当前正在导航到的点位下标
_error_msg      = ""            # 最近一次失败的原因

# 控制标志(不需要加锁,Python GIL + 简单 bool 写/读已够用)
_pause_flag     = False         # True = 导航线程应当暂停
_cancel_flag    = False         # True = 导航线程应当取消并退出

# ROS
_mb_client      = None          # actionlib.SimpleActionClient for move_base
_status_pub     = None          # Publisher to /nav_multi/status
_arrived_pub    = None          # Publisher to /nav_multi/point_arrived
_nav_thread     = None          # 导航后台线程

# 到点后短暂等待车身停稳再发事件;环境变量可调,0=不等待
_ARRIVE_SETTLE_S = float(os.environ.get("NAV_MULTI_ARRIVE_SETTLE_S", "0.5"))


# ============================================================
# 工具函数
# ============================================================

def _make_move_base_goal(point):
    """将点位 dict 转成 MoveBaseGoal。"""
    goal = MoveBaseGoal()
    goal.target_pose.header.frame_id = "map"
    goal.target_pose.header.stamp    = rospy.Time.now()
    goal.target_pose.pose.position.x  = float(point["positionX"])
    goal.target_pose.pose.position.y  = float(point["positionY"])
    goal.target_pose.pose.position.z  = float(point.get("positionZ", 0.0))
    goal.target_pose.pose.orientation.x = float(point.get("orientationX", 0.0))
    goal.target_pose.pose.orientation.y = float(point.get("orientationY", 0.0))
    goal.target_pose.pose.orientation.z = float(point.get("orientationZ", 0.0))
    goal.target_pose.pose.orientation.w = float(point.get("orientationW", 1.0))
    return goal


def _publish_point_arrived(point):
    """发布包含动作和播报文本的到点事件,不在 ROS 节点内执行副作用。"""
    if _ARRIVE_SETTLE_S > 0:
        rospy.sleep(rospy.Duration.from_sec(_ARRIVE_SETTLE_S))
    event = {
        "taskId": _task_id,
        "taskName": _task_name,
        "pointIndex": _current_index,
        "pointName": point.get("pointName", ""),
        "action": point.get("action", ""),
        "actionContent": point.get("actionContent", ""),
    }
    _arrived_pub.publish(String(data=json.dumps(event, ensure_ascii=False)))
    rospy.loginfo("[NavMulti] 已发布到点事件: %s", event)

def _build_status_dict():
    """构建当前状态快照(不加锁,调用方保证线程安全或在 Timer 回调中调用)。"""
    return {
        "state":             _state,
        "taskId":            _task_id,
        "taskName":          _task_name,
        "currentPointIndex": _current_index,
        "totalPoints":       len(_task_points),
        "currentPointName":  _task_points[_current_index]["pointName"]
                             if _task_points and _current_index < len(_task_points)
                             else "",
        "error":             _error_msg,
    }


# ============================================================
# 导航后台线程
# ============================================================

def _nav_thread_func():
    """导航主循环,在独立线程中运行。

    流程:
      对 _task_points[_current_index:] 依次发送 move_base goal。
      - 暂停: cancel 当前 goal,停在原地,等待 _pause_flag 变 False 后重新发同一个点。
      - 取消: cancel 当前 goal,退出循环,状态置 IDLE。
      - 失败: 记录错误,状态置 FAILED,退出。
      - 全部完成: 状态置 COMPLETED。
    """
    global _state, _current_index, _error_msg, _pause_flag, _cancel_flag

    rospy.loginfo("[NavMulti] 导航线程启动, 共 %d 个点位", len(_task_points))

    while _current_index < len(_task_points):

        # --- 检查取消 ---
        if _cancel_flag:
            rospy.loginfo("[NavMulti] 任务已取消")
            with _state_lock:
                _state = STATE_IDLE
            return

        # --- 等待 resume ---
        if _pause_flag:
            rospy.sleep(0.1)
            continue

        point = _task_points[_current_index]
        rospy.loginfo("[NavMulti] 导航到第 %d/%d 个点位: %s",
                      _current_index + 1, len(_task_points), point["pointName"])

        goal = _make_move_base_goal(point)
        _mb_client.send_goal(goal)

        # 等待 move_base 完成,每 0.5s 检查一次控制标志
        goal_interrupted = False
        while True:
            done = _mb_client.wait_for_result(rospy.Duration(0.5))
            if done:
                break
            if _cancel_flag:
                _mb_client.cancel_goal()
                rospy.loginfo("[NavMulti] 取消中(导航进行时)")
                with _state_lock:
                    _state = STATE_IDLE
                return
            if _pause_flag:
                _mb_client.cancel_goal()
                rospy.loginfo("[NavMulti] 暂停(已 cancel 当前 goal,等待 resume)")
                goal_interrupted = True
                break

        if goal_interrupted:
            # 暂停后回到循环顶部,_pause_flag 变 False 才会重新发 goal
            continue

        # --- 检查 move_base 结果 ---
        mb_state = _mb_client.get_state()
        if mb_state == GoalStatus.SUCCEEDED:
            rospy.loginfo("[NavMulti] 到达点位: %s", point["pointName"])
            _publish_point_arrived(point)
            with _state_lock:
                _current_index += 1
        else:
            err = "导航到点位 '%s' 失败 (move_base 状态码: %d)" % (point["pointName"], mb_state)
            rospy.logwarn("[NavMulti] %s", err)
            with _state_lock:
                _error_msg = err
                _state     = STATE_FAILED
            return

    # 全部点位完成
    rospy.loginfo("[NavMulti] 任务完成,共 %d 个点位", len(_task_points))
    with _state_lock:
        _state = STATE_COMPLETED


# ============================================================
# Service 回调
# ============================================================

def _handle_execute(req):
    """Service /nav_multi/execute 的 handler。

    req.data: JSON 字符串,格式:
    {
        "taskId":   3,
        "taskName": "展厅巡检",
        "points":   [
            {"pointName":"A", "positionX":1.0, "positionY":2.0,
             "orientationZ":0.0, "orientationW":1.0},
            ...
        ]
    }
    """
    global _state, _task_id, _task_name, _task_points, \
           _current_index, _error_msg, _pause_flag, _cancel_flag, _nav_thread

    # 解析 JSON
    try:
        data = json.loads(req.data)
    except (ValueError, TypeError) as e:
        return NavCommandResponse(success=False, message="JSON 解析失败: %s" % e)

    points = data.get("points", [])
    if not points:
        return NavCommandResponse(success=False, message="points 列表为空")

    # 检查是否有任务正在运行
    with _state_lock:
        if _state in (STATE_RUNNING, STATE_PAUSED):
            return NavCommandResponse(success=False,
                                      message="当前有任务正在执行(state=%s),请先取消" % _state)

    # 等待 move_base action server
    rospy.loginfo("[NavMulti] 等待 move_base action server...")
    if not _mb_client.wait_for_server(rospy.Duration(5.0)):
        return NavCommandResponse(success=False,
                                  message="move_base action server 未就绪(超时 5s)")

    # 初始化状态
    with _state_lock:
        _task_id       = data.get("taskId")
        _task_name     = data.get("taskName", "")
        _task_points   = points
        _current_index = 0
        _error_msg     = ""
        _pause_flag    = False
        _cancel_flag   = False
        _state         = STATE_RUNNING

    # 启动导航后台线程
    _nav_thread = threading.Thread(target=_nav_thread_func, daemon=True)
    _nav_thread.start()

    rospy.loginfo("[NavMulti] 任务已接收: %s, 共 %d 个点位",
                  _task_name, len(points))
    return NavCommandResponse(success=True,
                              message="任务已开始: %s" % _task_name)


def _handle_pause(req):
    """Service /nav_multi/pause 的 handler。"""
    global _pause_flag, _state

    with _state_lock:
        if _state != STATE_RUNNING:
            return TriggerResponse(success=False,
                                   message="当前不在 RUNNING 状态(state=%s)" % _state)
        _pause_flag = True
        _state      = STATE_PAUSED

    rospy.loginfo("[NavMulti] 已暂停")
    return TriggerResponse(success=True, message="已暂停")


def _handle_resume(req):
    """Service /nav_multi/resume 的 handler。"""
    global _pause_flag, _state

    with _state_lock:
        if _state != STATE_PAUSED:
            return TriggerResponse(success=False,
                                   message="当前不在 PAUSED 状态(state=%s)" % _state)
        _pause_flag = False
        _state      = STATE_RUNNING

    rospy.loginfo("[NavMulti] 已恢复")
    return TriggerResponse(success=True, message="已恢复")


def _handle_cancel(req):
    """Service /nav_multi/cancel 的 handler。"""
    global _cancel_flag, _pause_flag

    with _state_lock:
        if _state not in (STATE_RUNNING, STATE_PAUSED):
            return TriggerResponse(success=False,
                                   message="当前无正在执行的任务(state=%s)" % _state)
        _pause_flag  = False   # 解除暂停,让导航线程能看到 cancel_flag
        _cancel_flag = True

    rospy.loginfo("[NavMulti] 取消请求已发送")
    return TriggerResponse(success=True, message="取消指令已发送,机器人即将停止")


# ============================================================
# 状态发布(Timer 回调,1Hz)
# ============================================================

def _publish_status_cb(event):
    """定时发布 /nav_multi/status (1Hz)。"""
    with _state_lock:
        status = _build_status_dict()
    _status_pub.publish(String(data=json.dumps(status, ensure_ascii=False)))


# ============================================================
# 主入口
# ============================================================

def main():
    global _mb_client, _status_pub, _arrived_pub

    rospy.init_node("nav_multi", anonymous=False)
    rospy.loginfo("[NavMulti] 节点启动")

    # move_base action client
    _mb_client = actionlib.SimpleActionClient("move_base", MoveBaseAction)

    # 状态发布器
    _status_pub = rospy.Publisher("/nav_multi/status", String,
                                  queue_size=1, latch=True)

    # 非锁存到点事件;FastAPI 订阅后按 action/actionContent 执行。
    _arrived_pub = rospy.Publisher("/nav_multi/point_arrived", String,
                                   queue_size=10)

    # 注册 service servers
    rospy.Service("/nav_multi/execute", NavCommand, _handle_execute)
    rospy.Service("/nav_multi/pause",   Trigger,    _handle_pause)
    rospy.Service("/nav_multi/resume",  Trigger,    _handle_resume)
    rospy.Service("/nav_multi/cancel",  Trigger,    _handle_cancel)

    # 1Hz 定时发布状态
    rospy.Timer(rospy.Duration(1.0), _publish_status_cb)

    rospy.loginfo("[NavMulti] 就绪,等待任务")
    rospy.spin()


if __name__ == "__main__":
    main()
