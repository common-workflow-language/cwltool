# Stubs for rdflib.term (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

class Node: ...

class Identifier(Node, str):
    def __new__(cls, value: Any): ...
    def eq(self, other: Any): ...
    def neq(self, other: Any): ...
    def __ne__(self, other: Any): ...
    def __eq__(self, other: Any): ...
    def __gt__(self, other: Any): ...
    def __lt__(self, other: Any): ...
    def __le__(self, other: Any): ...
    def __ge__(self, other: Any): ...
    def __hash__(self): ...

class URIRef(Identifier):
    def __new__(cls, value: Any, base: Optional[Any] = ...): ...
    def toPython(self): ...
    def n3(self, namespace_manager: Optional[Any] = ...): ...
    def defrag(self): ...
    def __reduce__(self): ...
    def __getnewargs__(self): ...
    def __add__(self, other: Any): ...
    def __radd__(self, other: Any): ...
    def __mod__(self, other: Any): ...
    def md5_term_hash(self): ...
    def de_skolemize(self): ...

class Genid(URIRef): ...
class RDFLibGenid(Genid): ...

class BNode(Identifier):
    def __new__(cls, value=None, _sn_gen=..., _prefix=...): ...
    def toPython(self): ...
    def n3(self, namespace_manager=None): ...
    def __getnewargs__(self): ...
    def __reduce__(self): ...
    def md5_term_hash(self): ...
    def skolemize(self, authority=''): ...

class Literal(Identifier):
    __doc__ = ... # type: Any
    def __new__(cls, lexical_or_value, lang=None, datatype=None, normalize=None): ...
    def normalize(self): ...
    @property
    def value(self): ...
    @property
    def language(self): ...
    @property
    def datatype(self): ...
    def __reduce__(self): ...
    def __add__(self, val): ...
    def __nonzero__(self): ...
    def __neg__(self): ...
    def __pos__(self): ...
    def __abs__(self): ...
    def __invert__(self): ...
    def __gt__(self, other): ...
    def __lt__(self, other): ...
    def __le__(self, other): ...
    def __ge__(self, other): ...
    def __hash__(self): ...
    def __eq__(self, other): ...
    def eq(self, other): ...
    def neq(self, other): ...
    def n3(self, namespace_manager=None): ...
    def toPython(self): ...
    def md5_term_hash(self): ...

def bind(datatype, pythontype, constructor=None, lexicalizer=None): ...

class Variable(Identifier):
    def __new__(cls, value): ...
    def toPython(self): ...
    def n3(self, namespace_manager=None): ...
    def __reduce__(self): ...
    def md5_term_hash(self): ...

class Statement(Node, tuple):
    def __new__(cls, __tuple_arg_2, context): ...
    def __reduce__(self): ...
    def toPython(self): ...
