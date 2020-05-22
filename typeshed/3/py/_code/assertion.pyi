from typing import Any

BuiltinAssertionError: Any

class AssertionError(BuiltinAssertionError):
    msg: Any = ...
    args: Any = ...
    def __init__(self, *args: Any) -> None: ...

reinterpret_old: str
