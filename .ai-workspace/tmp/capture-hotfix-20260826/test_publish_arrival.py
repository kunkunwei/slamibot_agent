"""测试：向 /nav_multi/point_arrived 发布一个 action=photo 事件。"""
import json
import time

import rospy
from std_msgs.msg import String

rospy.init_node("test_arrival_pub", anonymous=True)
pub = rospy.Publisher("/nav_multi/point_arrived", String, queue_size=10)
time.sleep(1)
evt = {
    "runId": "test",
    "arrivalId": "test-arr-20260826-002",
    "taskId": 1,
    "pointIndex": 0,
    "pointName": "链路测试点",
    "action": "photo",
    "actionContent": "",
}
pub.publish(String(data=json.dumps(evt, ensure_ascii=False)))
print("published:", json.dumps(evt, ensure_ascii=False))
time.sleep(1)
