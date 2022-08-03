from typing import IO, Any, Dict, Iterator, List, Mapping, Optional, Tuple, overload

from rdflib import URIRef, Variable
from rdflib.term import Identifier
from typing_extensions import SupportsIndex

class ResultRow(Tuple["Identifier", ...]):
    def __new__(
        cls, values: Mapping[Variable, Identifier], labels: List[Variable]
    ) -> ResultRow: ...
    def __getattr__(self, name: str) -> Identifier: ...
    @overload
    def __getitem__(self, name: str) -> Identifier: ...
    @overload
    def __getitem__(self, __x: SupportsIndex) -> Identifier: ...
    @overload
    def __getitem__(self, __x: slice) -> Tuple[Identifier, ...]: ...
    def get(self, name: str, default: Any | None = ...) -> Identifier: ...
    def asdict(self) -> Dict[str, Identifier]: ...

class Result:
    type: Any
    vars: Any
    askAnswer: Any
    graph: Any
    def __init__(self, type_: str) -> None: ...
    bindings: Any
    def __iter__(self) -> Iterator[bool | ResultRow]: ...
    @staticmethod
    def parse(
        source: IO[Any] | None = ...,
        format: str | None = ...,
        content_type: str | None = ...,
        **kwargs: Any
    ) -> Result: ...
    def serialize(
        self,
        destination: str | IO[Any] | None = ...,
        encoding: str = ...,
        format: str = ...,
        **args: Any
    ) -> Optional[bytes]: ...
