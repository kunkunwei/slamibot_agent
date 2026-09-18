from intent_router import route

CFG = {
    'come_here': ['过来', '到我这儿'],
    'nav_cancel': ['取消导航', '不去了'],
    'nav_pause': ['暂停导航'],
    'nav_resume': ['继续导航'],
    'stand_up': ['站起来', '站立', '起身'],
    'lie_down': ['趴下', '蹲下', '卧倒'],
    'wave': ['招手', '打招呼', '挥挥手'],
}


def test_come_here():
    assert route('你过来一下', CFG).name == 'come_here'


def test_cancel():
    assert route('取消导航', CFG).name == 'nav_cancel'


def test_goto_heuristic():
    assert route('去前台', CFG).name == 'goto_point'


def test_chat_fallback():
    assert route('今天天气怎么样', CFG).name == 'chat'


def test_stand_up():
    assert route('你站起来', CFG).name == 'stand_up'


def test_lie_down():
    assert route('趴下', CFG).name == 'lie_down'


def test_wave():
    assert route('跟我打招呼', CFG).name == 'wave'
