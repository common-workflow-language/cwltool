from typing import Any, Optional

BaseException = BaseException
GeneratorExit = GeneratorExit
all = all
any = any
callable = callable
enumerate = enumerate
reversed = reversed
set: Any
frozenset: Any
sorted = sorted
text = str
bytes = bytes

def execfile(fn: Any, globs: Optional[Any] = ..., locs: Optional[Any] = ...) -> None: ...
