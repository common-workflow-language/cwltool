# Stubs for networkx.generators.random_graphs (Python 3.5)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

def fast_gnp_random_graph(n, p, seed: Optional[Any] = ..., directed: bool = ...): ...
def gnp_random_graph(n, p, seed: Optional[Any] = ..., directed: bool = ...): ...
binomial_graph = gnp_random_graph
erdos_renyi_graph = gnp_random_graph

def dense_gnm_random_graph(n, m, seed: Optional[Any] = ...): ...
def gnm_random_graph(n, m, seed: Optional[Any] = ..., directed: bool = ...): ...
def newman_watts_strogatz_graph(n, k, p, seed: Optional[Any] = ...): ...
def watts_strogatz_graph(n, k, p, seed: Optional[Any] = ...): ...
def connected_watts_strogatz_graph(n, k, p, tries: int = ..., seed: Optional[Any] = ...): ...
def random_regular_graph(d, n, seed: Optional[Any] = ...): ...
def barabasi_albert_graph(n, m, seed: Optional[Any] = ...): ...
def extended_barabasi_albert_graph(n, m, p, q, seed: Optional[Any] = ...): ...
def powerlaw_cluster_graph(n, m, p, seed: Optional[Any] = ...): ...
def random_lobster(n, p1, p2, seed: Optional[Any] = ...): ...
def random_shell_graph(constructor, seed: Optional[Any] = ...): ...
def random_powerlaw_tree(n, gamma: int = ..., seed: Optional[Any] = ..., tries: int = ...): ...
def random_powerlaw_tree_sequence(n, gamma: int = ..., seed: Optional[Any] = ..., tries: int = ...): ...
def random_kernel_graph(n, kernel_integral, kernel_root: Optional[Any] = ..., seed: Optional[Any] = ...): ...
