from __future__ import absolute_import

from typing import Any, Callable, List, cast

# http://rightfootin.blogspot.com/2006/09/more-on-python-flatten.html


def flatten(l, ltypes=(list, tuple)):
    # type: (Any, Any) -> List[Any]
    if l is None:
        return []
    if not isinstance(l, ltypes):
        return [l]

    ltype = type(l)
    l = list(l)
    i = 0
    while i < len(l):
        while isinstance(l[i], ltypes):
            if not l[i]:
                l.pop(i)
                i -= 1
                break
            else:
                l[i:i + 1] = l[i]
        i += 1
    return cast(Callable[[Any], List], ltype)(l)
