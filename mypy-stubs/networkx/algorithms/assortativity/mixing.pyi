# Stubs for networkx.algorithms.assortativity.mixing (Python 3.5)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

def attribute_mixing_dict(
    G, attribute, nodes: Optional[Any] = ..., normalized: bool = ...
): ...
def attribute_mixing_matrix(
    G,
    attribute,
    nodes: Optional[Any] = ...,
    mapping: Optional[Any] = ...,
    normalized: bool = ...,
): ...
def degree_mixing_dict(
    G,
    x: str = ...,
    y: str = ...,
    weight: Optional[Any] = ...,
    nodes: Optional[Any] = ...,
    normalized: bool = ...,
): ...
def degree_mixing_matrix(
    G,
    x: str = ...,
    y: str = ...,
    weight: Optional[Any] = ...,
    nodes: Optional[Any] = ...,
    normalized: bool = ...,
): ...
def numeric_mixing_matrix(
    G, attribute, nodes: Optional[Any] = ..., normalized: bool = ...
): ...
def mixing_dict(xy, normalized: bool = ...): ...
