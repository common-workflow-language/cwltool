# Stubs for rdflib.graph (Python 3)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from rdflib.term import Identifier, Node, BNode
from typing import Any, Iterator, IO, Optional, Text, Tuple, Union

class Graph(Node):
    context_aware: bool = ...
    formula_aware: bool = ...
    default_union: bool = ...
    def __init__(self, store: str = ..., identifier: Optional[Any] = ..., namespace_manager: Optional[Any] = ...) -> None: ...
    store: Any = ...
    identifier: Any = ...
    namespace_manager: Any = ...
    def toPython(self): ...
    def destroy(self, configuration: Any) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def open(self, configuration: Any, create: bool = ...): ...
    def close(self, commit_pending_transaction: bool = ...) -> None: ...
    def add(self, xxx_todo_changeme: Any) -> None: ...
    def addN(self, quads: Any) -> None: ...
    def remove(self, xxx_todo_changeme1: Any) -> None: ...
    def triples(self, xxx_todo_changeme2: Tuple[Optional[Union[Text, BNode]], Optional[Union[Text, BNode]], Optional[BNode]]) -> Iterator[Tuple[BNode, BNode, BNode]]: ...
    def __getitem__(self, item: Any): ...
    def __len__(self): ...
    def __iter__(self): ...
    def __contains__(self, triple: Any): ...
    def __hash__(self): ...
    def md5_term_hash(self): ...
    def __cmp__(self, other: Any): ...
    def __eq__(self, other: Any): ...
    def __lt__(self, other: Any): ...
    def __le__(self, other: Any): ...
    def __gt__(self, other: Any): ...
    def __ge__(self, other: Any): ...
    def __iadd__(self, other: Any): ...
    def __isub__(self, other: Any): ...
    def __add__(self, other: Any): ...
    def __mul__(self, other: Any): ...
    def __sub__(self, other: Any): ...
    def __xor__(self, other: Any): ...
    __or__: Any = ...
    __and__: Any = ...
    def set(self, triple: Any) -> None: ...
    def subjects(self, predicate: Optional[Any] = ..., object: Optional[Any] = ...) -> None: ...
    def predicates(self, subject: Optional[Any] = ..., object: Optional[Any] = ...) -> None: ...
    def objects(self, subject: Optional[Any] = ..., predicate: Optional[Any] = ...) -> None: ...
    def subject_predicates(self, object: Optional[Any] = ...) -> None: ...
    def subject_objects(self, predicate: Optional[Any] = ...) -> None: ...
    def predicate_objects(self, subject: Optional[Any] = ...) -> None: ...
    def triples_choices(self, xxx_todo_changeme3: Any, context: Optional[Any] = ...) -> None: ...
    def value(self, subject: Optional[Any] = ..., predicate: Any = ..., object: Optional[Any] = ..., default: Optional[Any] = ..., any: bool = ...): ...
    def label(self, subject: Any, default: str = ...): ...
    def preferredLabel(self, subject: Any, lang: Optional[Any] = ..., default: Optional[Any] = ..., labelProperties: Any = ...): ...
    def comment(self, subject: Any, default: str = ...): ...
    def items(self, list: Any) -> None: ...
    def transitiveClosure(self, func: Any, arg: Any, seen: Optional[Any] = ...) -> None: ...
    def transitive_objects(self, subject: Any, property: Any, remember: Optional[Any] = ...) -> None: ...
    def transitive_subjects(self, predicate: Any, object: Any, remember: Optional[Any] = ...) -> None: ...
    def seq(self, subject: Any): ...
    def qname(self, uri: Any): ...
    def compute_qname(self, uri: Any, generate: bool = ...): ...
    def bind(self, prefix: Any, namespace: Any, override: bool = ...): ...
    def namespaces(self) -> None: ...
    def absolutize(self, uri: Any, defrag: int = ...): ...
    def serialize(self, destination: Optional[Any] = ..., format: str = ..., base: Optional[Any] = ..., encoding: Optional[Any] = ..., **args: Any): ...
    def parse(self, source: Optional[Any] = ..., publicID: Optional[Any] = ..., format: Optional[Any] = ..., location: Optional[Any] = ..., file: Optional[Any] = ..., data: Optional[Any] = ..., **args: Any): ...
    def load(self, source: Any, publicID: Optional[Any] = ..., format: str = ...) -> None: ...
    def query(self, query_object: Any, processor: str = ..., result: str = ..., initNs: Optional[Any] = ..., initBindings: Optional[Any] = ..., use_store_provided: bool = ..., **kwargs: Any): ...
    def update(self, update_object: Any, processor: str = ..., initNs: Optional[Any] = ..., initBindings: Optional[Any] = ..., use_store_provided: bool = ..., **kwargs: Any): ...
    def n3(self): ...
    def __reduce__(self): ...
    def isomorphic(self, other: Any): ...
    def connected(self): ...
    def all_nodes(self): ...
    def collection(self, identifier: Any): ...
    def resource(self, identifier: Any): ...
    def skolemize(self, new_graph: Optional[Any] = ..., bnode: Optional[Any] = ...): ...
    def de_skolemize(self, new_graph: Optional[Any] = ..., uriref: Optional[Any] = ...): ...

class ConjunctiveGraph(Graph):
    context_aware: bool = ...
    default_union: bool = ...
    default_context: Any = ...
    def __init__(self, store: str = ..., identifier: Optional[Any] = ...) -> None: ...
    def __contains__(self, triple_or_quad: Any): ...
    def add(self, triple_or_quad: Any) -> None: ...
    def addN(self, quads: Any) -> None: ...
    def remove(self, triple_or_quad: Any) -> None: ...
    def triples(self, xxx_todo_changeme2: Tuple[Optional[Union[Text, BNode]], Optional[Union[Text, BNode]], Optional[BNode]]) -> Iterator[Tuple[BNode, BNode, BNode]]: ...
    def quads(self, triple_or_quad: Optional[Any] = ...) -> None: ...
    def triples_choices(self, xxx_todo_changeme4: Any, context: Optional[Any] = ...) -> None: ...
    def __len__(self): ...
    def contexts(self, triple: Optional[Any] = ...) -> None: ...
    def get_context(self, identifier: Any, quoted: bool = ...): ...
    def remove_context(self, context: Any) -> None: ...
    def context_id(self, uri: Any, context_id: Optional[Any] = ...): ...
    def parse(self, source: Optional[Any] = ..., publicID: Optional[Any] = ..., format: Optional[Any] = ..., location: Optional[Any] = ..., file: Optional[Any] = ..., data: Optional[Any] = ..., **args: Any): ...
    def __reduce__(self): ...

class Dataset(ConjunctiveGraph):
    __doc__: Any = ...
    default_context: Any = ...
    default_union: Any = ...
    def __init__(self, store: str = ..., default_union: bool = ...) -> None: ...
    def graph(self, identifier: Optional[Any] = ...): ...
    def parse(self, source: Optional[Any] = ..., publicID: Optional[Any] = ..., format: Optional[Any] = ..., location: Optional[Any] = ..., file: Optional[Any] = ..., data: Optional[Any] = ..., **args: Any): ...
    def add_graph(self, g: Any): ...
    def remove_graph(self, g: Any) -> None: ...
    def contexts(self, triple: Optional[Any] = ...) -> None: ...
    graphs: Any = ...
    def quads(self, triple_or_quad: Optional[Any] = ...) -> None: ...

class QuotedGraph(Graph):
    def __init__(self, store: Any, identifier: Any) -> None: ...
    def add(self, xxx_todo_changeme5: Any) -> None: ...
    def addN(self, quads: Any) -> None: ...
    def n3(self): ...
    def __reduce__(self): ...

class Seq:
    def __init__(self, graph: Any, subject: Any) -> None: ...
    def toPython(self): ...
    def __iter__(self) -> None: ...
    def __len__(self): ...
    def __getitem__(self, index: Any): ...

class ModificationException(Exception):
    def __init__(self) -> None: ...

class UnSupportedAggregateOperation(Exception):
    def __init__(self) -> None: ...

class ReadOnlyGraphAggregate(ConjunctiveGraph):
    graphs: Any = ...
    def __init__(self, graphs: Any, store: str = ...) -> None: ...
    def destroy(self, configuration: Any) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def open(self, configuration: Any, create: bool = ...) -> None: ...
    def close(self, commit_pending_transaction: bool = ...) -> None: ...
    def add(self, xxx_todo_changeme6: Any) -> None: ...
    def addN(self, quads: Any) -> None: ...
    def remove(self, xxx_todo_changeme7: Any) -> None: ...
    def triples(self, xxx_todo_changeme2: Tuple[Optional[Union[Text, BNode]], Optional[Union[Text, BNode]], Optional[BNode]]) -> Iterator[Tuple[BNode, BNode, BNode]]: ...
    def __contains__(self, triple_or_quad: Any): ...
    def quads(self, triple_or_quad: Optional[Any] = ...) -> None: ...
    def __len__(self): ...
    def __cmp__(self, other: Any): ...
    def __iadd__(self, other: Any) -> None: ...
    def __isub__(self, other: Any) -> None: ...
    def triples_choices(self, xxx_todo_changeme10: Any, context: Optional[Any] = ...) -> None: ...
    def qname(self, uri: Any): ...
    def compute_qname(self, uri: Any, generate: bool = ...): ...
    def bind(self, prefix: Any, namespace: Any, override: bool = ...) -> None: ...
    def namespaces(self) -> None: ...
    def absolutize(self, uri: Any, defrag: int = ...) -> None: ...
    def parse(self, source: Optional[Any] = ..., publicID: Optional[Any] = ..., format: Optional[Any] = ..., location: Optional[Any] = ..., file: Optional[Any] = ..., data: Optional[Any] = ..., **args: Any): ...
    def n3(self) -> None: ...
