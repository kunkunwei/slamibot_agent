"""意图 → /voice_command 字符串映射（不依赖 ROS）。"""
import pytest

from intent_router import Intent
from robot_cmd_publisher import RobotCmdError, intent_to_command, intent_to_tts


@pytest.mark.parametrize(
    'name,text,expected',
    [
        ('come_here', '过来', 'come_here'),
        ('nav_cancel', '取消导航', 'nav_cancel'),
        ('nav_pause', '暂停一下', 'nav_pause'),
        ('nav_resume', '继续导航', 'nav_resume'),
        ('stand_up', '站起来', 'stand_up'),
        ('lie_down', '趴下', 'lie_down'),
        ('wave', '招手', 'wave'),
        ('goto_point', '去客厅', 'goto:去客厅'),
    ],
)
def test_intent_to_command(name, text, expected):
    assert intent_to_command(Intent(name=name, text=text)) == expected


def test_goto_empty_raises():
    with pytest.raises(RobotCmdError, match='缺少文本'):
        intent_to_command(Intent(name='goto_point', text='  '))


def test_unknown_intent_raises():
    with pytest.raises(RobotCmdError, match='未知意图'):
        intent_to_command(Intent(name='chat', text='你好'))


def test_intent_to_tts():
    assert intent_to_tts(Intent(name='wave', text='招手')) == '你好呀'
    assert intent_to_tts(Intent(name='goto_point', text='去前台')) == '好的，去前台'
