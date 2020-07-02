from typing import Any, Callable, List, cast

# http://rightfootin.blogspot.com/2006/09/more-on-python-flatten.html


def flatten(thing, ltypes=(list, tuple)):
    # type: (Any, Any) -> List[Any]
    if thing is None:
        return []
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
    return cast(Callable[[Any], List[Any]], ltype)(thing_list)
