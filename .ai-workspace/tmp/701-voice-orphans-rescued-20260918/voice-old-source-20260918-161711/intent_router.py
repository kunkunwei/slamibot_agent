"""语音控狗意图路由（规则优先）。"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Intent:
    name: str
    text: str


def _hit(text: str, phrases: List[str]) -> bool:
    return any(p and p in text for p in phrases)


def route(text: str, intent_cfg: Dict[str, List[str]]) -> Intent:
    t = (text or '').strip()
    order = [
        'come_here',
        'nav_cancel',
        'nav_pause',
        'nav_resume',
        'stand_up',
        'lie_down',
        'wave',
    ]
    for name in order:
        if _hit(t, intent_cfg.get(name, [])):
            return Intent(name=name, text=t)
    if t.startswith('去') or t.startswith('到') or '导航到' in text:
        return Intent(name='goto_point', text=t)
    return Intent(name='chat', text=t)
