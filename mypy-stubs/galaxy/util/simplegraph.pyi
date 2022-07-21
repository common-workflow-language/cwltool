from collections.abc import Generator

from _typeshed import Incomplete

class SimpleGraphNode:
    index: Incomplete
    data: Incomplete
    def __init__(self, index, **data) -> None: ...

class SimpleGraphEdge:
    source_index: Incomplete
    target_index: Incomplete
    data: Incomplete
    def __init__(self, source_index, target_index, **data) -> None: ...

class SimpleGraph:
    nodes: Incomplete
    edges: Incomplete
    def __init__(
        self, nodes: Incomplete | None = ..., edges: Incomplete | None = ...
    ) -> None: ...
    def add_node(self, node_id, **data): ...
    def add_edge(self, source_id, target_id, **data): ...
    def gen_node_dicts(self) -> Generator[Incomplete, None, None]: ...
    def gen_edge_dicts(self) -> Generator[Incomplete, None, None]: ...
    def as_dict(self): ...
