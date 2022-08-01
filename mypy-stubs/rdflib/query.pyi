from io import BufferedIOBase
from typing import Any, Dict, Iterator, List, Optional, Tuple, overload

from rdflib import URIRef, Variable
from typing_extensions import SupportsIndex

class ResultRow:  # Tuple[Variable, URIRef]):
    def __new__(
        cls, values: Dict[Variable, URIRef], labels: List[Variable]
    ) -> ResultRow: ...
    def __getattr__(self, name: str) -> Any: ...
    @overload
    def __getitem__(self, name: str) -> URIRef: ...
    @overload
    def __getitem__(self, __x: SupportsIndex) -> Variable | URIRef: ...
    @overload
    def __getitem__(self, __x: slice) -> Tuple[Variable | URIRef, ...]: ...
    def get(self, name: str, default: Any | None = ...) -> URIRef: ...
    def asdict(self) -> Dict[Variable, URIRef]: ...

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
        source: str | None = ...,
        format: str | None = ...,
        content_type: str | None = ...,
        **kwargs: Any
    ) -> Result: ...
    def serialize(
        self,
        destination: str | BufferedIOBase | None = ...,
        encoding: str = ...,
        format: str = ...,
        **args: Any
    ) -> Optional[bytes]: ...
