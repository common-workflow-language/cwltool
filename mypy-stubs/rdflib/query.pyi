from io import BufferedIOBase
from typing import Any, Dict, Optional, Union

class Result:
    type: Any
    vars: Any
    askAnswer: Any
    graph: Any
    def __init__(self, type_: str) -> None: ...
    bindings: Any
    @staticmethod
    def parse(
        source: Any | None = ...,
        format: Any | None = ...,
        content_type: Any | None = ...,
        **kwargs: Any
    ) -> Any: ...
    def serialize(
        self,
        destination: Optional[Union[str, BufferedIOBase]] = ...,
        encoding: str = ...,
        format: str = ...,
        **args: Any
    ) -> Optional[bytes]: ...
