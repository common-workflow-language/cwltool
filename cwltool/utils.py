# no imports from cwltool allowed

from typing import Any, List, Optional, Tuple, Union


def aslist(l):  # type: (Any) -> List[Any]
    if isinstance(l, list):
        return l
    else:
        return [l]


def get_feature(self,    # type: Any
                feature  # type: Any
                ):  # type: (...) -> Union[Tuple[Any, bool], Tuple[None, None]]
    for t in reversed(self.requirements):
        if t["class"] == feature:
            return (t, True)
    for t in reversed(self.hints):
        if t["class"] == feature:
            return (t, False)
    return (None, None)
