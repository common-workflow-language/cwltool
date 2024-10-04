"""
Our version of the popular flatten() method.

http://rightfootin.blogspot.com/2006/09/more-on-python-flatten.html
"""

from typing import Any, Callable, cast


def flatten(thing: Any) -> list[Any]:
    """Flatten a list without recursion problems."""
    if thing is None:
        return []
    ltypes = (list, tuple)
    if not isinstance(thing, ltypes):
        return [thing]

    ltype = type(thing)
    thing_list = list(thing)
    i = 0
    while i < len(thing_list):
        while isinstance(thing_list[i], ltypes):
            if not thing_list[i]:
                thing_list.pop(i)
                i -= 1
                break
            else:
                thing_list[i : i + 1] = thing_list[i]
        i += 1
    return cast(Callable[[Any], list[Any]], ltype)(thing_list)
