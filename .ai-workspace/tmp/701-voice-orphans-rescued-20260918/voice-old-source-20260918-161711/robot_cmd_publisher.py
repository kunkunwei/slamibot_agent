"""ROS1 语音指令发布：std_msgs/String → /voice_command。"""
from __future__ import annotations

from intent_router import Intent


class RobotCmdError(Exception):
    """ROS 指令发布失败（禁止静默）。"""


# 意图名 → 话题字符串（goto_point 单独处理）
_INTENT_CMD = {
    'come_here': 'come_here',
    'nav_cancel': 'nav_cancel',
    'nav_pause': 'nav_pause',
    'nav_resume': 'nav_resume',
    'stand_up': 'stand_up',
    'lie_down': 'lie_down',
    'wave': 'wave',
}

_TTS_REPLY = {
    'come_here': '好的，我过来了',
    'nav_cancel': '已取消导航',
    'nav_pause': '已暂停导航',
    'nav_resume': '已继续导航',
    'stand_up': '好的，站起来了',
    'lie_down': '好的，趴下了',
    'wave': '你好呀',
}


def intent_to_command(intent: Intent) -> str:
    """意图 → /voice_command 的 data 字符串（纯函数，不依赖 ROS）。"""
    if intent.name == 'goto_point':
        text = (intent.text or '').strip()
        if not text:
            raise RobotCmdError('去点位意图缺少文本')
        return f'goto:{text}'
    cmd = _INTENT_CMD.get(intent.name)
    if not cmd:
        raise RobotCmdError(f'未知意图: {intent.name}')
    return cmd


def intent_to_tts(intent: Intent) -> str:
    """意图成功发布后的固定 TTS 文案。"""
    if intent.name == 'goto_point':
        text = (intent.text or '').strip()
        return f'好的，{text}' if text else '好的，正在导航'
    reply = _TTS_REPLY.get(intent.name)
    if not reply:
        raise RobotCmdError(f'未知意图: {intent.name}')
    return reply


class RobotCmdPublisher:
    """向 ROS1 话题发布动作字符串。"""

    def __init__(self, topic: str = '/voice_command', queue_size: int = 10):
        self.topic = topic or '/voice_command'
        self.queue_size = queue_size
        self._pub = None
        self._rospy = None

    def start(self) -> None:
        try:
            import rospy
            from std_msgs.msg import String
        except ImportError as e:
            raise RobotCmdError(
                '无法导入 rospy/std_msgs，请先 source ROS1 环境'
            ) from e

        self._rospy = rospy
        if not rospy.core.is_initialized():
            try:
                rospy.init_node('xf_voice_cmd', anonymous=True, disable_signals=True)
            except Exception as e:
                raise RobotCmdError(f'rospy.init_node 失败: {e}') from e

        try:
            self._pub = rospy.Publisher(self.topic, String, queue_size=self.queue_size)
            # 给 subscriber 一点连接时间
            rospy.sleep(0.2)
        except Exception as e:
            raise RobotCmdError(f'创建 Publisher 失败 ({self.topic}): {e}') from e

    def publish(self, action: str) -> None:
        if self._pub is None or self._rospy is None:
            raise RobotCmdError('Publisher 未启动，请先调用 start()')
        text = (action or '').strip()
        if not text:
            raise RobotCmdError('动作字符串为空')
        try:
            from std_msgs.msg import String
            msg = String()
            msg.data = text
            self._pub.publish(msg)
        except Exception as e:
            raise RobotCmdError(f'发布失败 topic={self.topic} data={text!r}: {e}') from e

    def publish_intent(self, intent: Intent) -> str:
        """发布意图对应字符串，返回 TTS 文案。"""
        cmd = intent_to_command(intent)
        self.publish(cmd)
        return intent_to_tts(intent)
