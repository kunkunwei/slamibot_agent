"""In-process control ownership latch for ROS1 navigation safety.

The latch closes the race where an old HTTP callback starts/resumes navigation
while manual takeover or mapping transition is already in progress.  It does
not replace ROS process state; it only fail-closes command admission.
"""

import threading


OWNER_AUTO = "AUTO"
OWNER_MANUAL_PENDING = "MANUAL_PENDING"
OWNER_MANUAL = "MANUAL"
OWNER_MAPPING_PENDING = "MAPPING_PENDING"
OWNER_MAPPING = "MAPPING"

_lock = threading.RLock()
_owner = OWNER_AUTO
_generation = 0


def claim(owner: str) -> dict:
    global _owner, _generation
    with _lock:
        _generation += 1
        _owner = owner
        return {"owner": _owner, "generation": _generation}


def snapshot() -> dict:
    with _lock:
        return {"owner": _owner, "generation": _generation}


def navigation_allowed() -> tuple[bool, str]:
    state = snapshot()
    if state["owner"] != OWNER_AUTO:
        return False, "CONTROL_OWNERSHIP_%s" % state["owner"]
    return True, ""
