from typing import Any


def aslist(l):  # type: (Any) -> List[Any]
    if isinstance(l, list):
        return l
    else:
        return [l]
