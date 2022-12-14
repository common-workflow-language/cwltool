from collections.abc import Generator
from typing import Any, Callable, Union

from rdflib.term import Node as Node
from rdflib.term import URIRef as URIRef

ZeroOrMore: str
OneOrMore: str
ZeroOrOne: str

class Path:
    __or__: Callable[[Path, Union["URIRef", "Path"]], "AlternativePath"]
    __invert__: Callable[[Path], "InvPath"]
    __neg__: Callable[[Path], "NegatedPath"]
    __truediv__: Callable[[Path, Union["URIRef", "Path"]], "SequencePath"]
    __mul__: Callable[[Path, str], "MulPath"]
    def __hash__(self) -> int: ...
    def __lt__(self, other: Any) -> bool: ...

class InvPath(Path): ...
class SequencePath(Path): ...
class AlternativePath(Path): ...
class MulPath(Path): ...
class NegatedPath(Path): ...
