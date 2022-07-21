# Stubs for networkx.classes.function (Python 3.5)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

def nodes(G): ...
def edges(G, nbunch: Optional[Any] = ...): ...
def degree(G, nbunch: Optional[Any] = ..., weight: Optional[Any] = ...): ...
def neighbors(G, n): ...
def number_of_nodes(G): ...
def number_of_edges(G): ...
def density(G): ...
def degree_histogram(G): ...
def is_directed(G): ...
def freeze(G): ...
def is_frozen(G): ...
def add_star(G_to_add_to, nodes_for_star, **attr): ...
def add_path(G_to_add_to, nodes_for_path, **attr): ...
def add_cycle(G_to_add_to, nodes_for_cycle, **attr): ...
def subgraph(G, nbunch): ...
def induced_subgraph(G, nbunch): ...
def edge_subgraph(G, edges): ...
def restricted_view(G, nodes, edges): ...
def reverse_view(digraph): ...
def to_directed(graph): ...
def to_undirected(graph): ...
def create_empty_copy(G, with_data: bool = ...): ...
def info(G, n: Optional[Any] = ...): ...
def set_node_attributes(G, values, name: Optional[Any] = ...): ...
def get_node_attributes(G, name): ...
def set_edge_attributes(G, values, name: Optional[Any] = ...): ...
def get_edge_attributes(G, name): ...
def all_neighbors(graph, node): ...
def non_neighbors(graph, node): ...
def non_edges(graph): ...
def common_neighbors(G, u, v): ...
def is_weighted(G, edge: Optional[Any] = ..., weight: str = ...): ...
def is_negatively_weighted(G, edge: Optional[Any] = ..., weight: str = ...): ...
def is_empty(G): ...
def nodes_with_selfloops(G): ...
def selfloop_edges(
    G, data: bool = ..., keys: bool = ..., default: Optional[Any] = ...
): ...
def number_of_selfloops(G): ...
