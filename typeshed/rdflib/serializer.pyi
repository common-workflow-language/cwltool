from typing import Any

class Serializer:
    store: Any
    encoding: str
    base: Any
    def __init__(self, store) -> None: ...
    def serialize(
        self, stream, base: Any | None = ..., encoding: Any | None = ..., **args
    ) -> None: ...
    def relativize(self, uri): ...
