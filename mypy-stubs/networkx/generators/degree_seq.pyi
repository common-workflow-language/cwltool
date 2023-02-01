# Stubs for networkx.generators.degree_seq (Python 3.5)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

def configuration_model(
    deg_sequence, create_using: Optional[Any] = ..., seed: Optional[Any] = ...
): ...
def directed_configuration_model(
    in_degree_sequence,
    out_degree_sequence,
    create_using: Optional[Any] = ...,
    seed: Optional[Any] = ...,
): ...
def expected_degree_graph(w, seed: Optional[Any] = ..., selfloops: bool = ...): ...
def havel_hakimi_graph(deg_sequence, create_using: Optional[Any] = ...): ...
def directed_havel_hakimi_graph(
    in_deg_sequence, out_deg_sequence, create_using: Optional[Any] = ...
): ...
def degree_sequence_tree(deg_sequence, create_using: Optional[Any] = ...): ...
def random_degree_sequence_graph(sequence, seed: Optional[Any] = ..., tries: int = ...): ...

class DegreeSequenceRandomGraph:
    degree: Any = ...
    m: Any = ...
    dmax: Any = ...
    def __init__(self, degree, seed: Optional[Any] = ...) -> None: ...
    remaining_degree: Any = ...
    graph: Any = ...
    def generate(self): ...
    def update_remaining(self, u, v, aux_graph: Optional[Any] = ...): ...
    def p(self, u, v): ...
    def q(self, u, v): ...
    def suitable_edge(self): ...
    def phase1(self): ...
    def phase2(self): ...
    def phase3(self): ...
