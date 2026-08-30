# -*- coding: utf-8 -*-
"""在板上 ros_client.py 精确插入 /robot_map_pose 转发（27 行，与本地 git diff 一致）。
基准：src_ros_client.py（板上 src=install 同内容）→ 输出 src_ros_client_patched.py"""
import io

SRC = "src_ros_client.py"
DST = "src_ros_client_patched.py"

with io.open(SRC, encoding="utf-8") as f:
    s = f.read()

def apply(old, new, tag):
    global s
    n = s.count(old)
    assert n == 1, "%s 锚点数量=%d (期望1)" % (tag, n)
    s = s.replace(old, new)

# 1. __init__: 新增发布器句柄
apply(
    "        self._pose_topic: Optional[roslibpy.Topic] = None\n",
    "        self._pose_topic: Optional[roslibpy.Topic] = None\n"
    "        self._robot_map_pose_pub: Optional[roslibpy.Topic] = None\n",
    "__init__",
)

# 2. start(): 创建发布器
apply(
    "        self._pose_topic.subscribe(self._on_pose)\n",
    "        self._pose_topic.subscribe(self._on_pose)\n"
    "        # 转发 /amcl_pose → /robot_map_pose（PoseStamped），供 APP 3D 点云箭头实时显示\n"
    "        self._robot_map_pose_pub = roslibpy.Topic(\n"
    "            self._ros,\n"
    "            \"/robot_map_pose\",\n"
    "            \"geometry_msgs/PoseStamped\",\n"
    "        )\n",
    "start",
)

# 3. stop(): 清空发布器句柄
apply(
    "        self._pose_topic = None\n",
    "        self._pose_topic = None\n"
    "        self._robot_map_pose_pub = None\n",
    "stop",
)

# 4. _on_pose 末尾调用转发 + 新增方法
apply(
    "        with self._lock:\n"
    "            self._latest_pose = value\n",
    "        with self._lock:\n"
    "            self._latest_pose = value\n"
    "        self._publish_robot_map_pose(message)\n"
    "\n"
    "    def _publish_robot_map_pose(self, message: dict[str, Any]) -> None:\n"
    "        \"\"\"转发最新 /amcl_pose 为 /robot_map_pose（PoseStamped, frame_id=map）。\"\"\"\n"
    "        if self._robot_map_pose_pub is None:\n"
    "            return\n"
    "        try:\n"
    "            header = message.get(\"header\", {})\n"
    "            stamped = {\n"
    "                \"header\": {\n"
    "                    \"seq\": header.get(\"seq\", 0),\n"
    "                    \"stamp\": header.get(\"stamp\", {\"secs\": 0, \"nsecs\": 0}),\n"
    "                    \"frame_id\": header.get(\"frame_id\", \"map\"),\n"
    "                },\n"
    "                \"pose\": message[\"pose\"][\"pose\"],\n"
    "            }\n"
    "            self._robot_map_pose_pub.publish(roslibpy.Message(stamped))\n"
    "        except Exception as exc:\n"
    "            LOGGER.warning(\"转发 /robot_map_pose 失败: %s\", exc)\n",
    "_on_pose",
)

with io.open(DST, "w", encoding="utf-8", newline="") as f:
    f.write(s)
print("patched OK ->", DST, "lines=", s.count("\n") + 1)
