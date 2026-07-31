"""Pure state helpers for the Gateway Observatory Perspective page."""

REVISION = u"observatory-v1"
_SCENES = (u"ORBIT", u"PULSE", u"TRACE")


def _require_index(value):
    if isinstance(value, bool) or type(value) not in (int, long):
        raise TypeError("scene index must be an integer")
    if value < 0 or value >= len(_SCENES):
        raise ValueError("scene index out of range")
    return int(value)


def next_scene(value):
    index = _require_index(value)
    return (index + 1) % len(_SCENES)


def scene_label(value):
    index = _require_index(value)
    return u"SCENE %02d / %s" % (index + 1, _SCENES[index])
