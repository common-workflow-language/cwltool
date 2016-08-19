# no imports from cwltool allowed

from typing import Any, Tuple

def aslist(l):  # type: (Any) -> List[Any]
    if isinstance(l, list):
        return l
    else:
        return [l]

def get_feature(self, feature):  # type: (Any, Any) -> Tuple[Any, bool]
    for t in reversed(self.requirements):
        if t["class"] == feature:
            return (t, True)
    for t in reversed(self.hints):
        if t["class"] == feature:
            return (t, False)
    return (None, None)
