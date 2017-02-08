# Stubs for rdflib.namespace (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Tuple, Union


class Namespace(unicode):
    __doc__ = ...  # type: Any

    def __new__(cls, value): ...

    @property
    def title(self): ...

    def term(self, name): ...

    def __getitem__(self, key, default=None): ...

    def __getattr__(self, name): ...


class URIPattern(unicode):
    __doc__ = ...  # type: Any

    def __new__(cls, value): ...

    def __mod__(self, *args, **kwargs): ...

    def format(self, *args, **kwargs): ...


class ClosedNamespace:
    uri = ...  # type: Any

    def __init__(self, uri, terms): ...

    def term(self, name): ...

    def __getitem__(self, key, default=None): ...

    def __getattr__(self, name): ...


class _RDFNamespace(ClosedNamespace):
    def __init__(self): ...

    def term(self, name): ...


RDF = ...  # type: Any
RDFS = ...  # type: Any
OWL = ...  # type: Any
XSD = ...  # type: Any
SKOS = ...  # type: Any
DOAP = ...  # type: Any
FOAF = ...  # type: Any
DC = ...  # type: Any
DCTERMS = ...  # type: Any
VOID = ...  # type: Any


class NamespaceManager:
    graph = ...  # type: Any

    def __init__(self, graph): ...

    def reset(self): ...

    store = ...  # type: Any

    def qname(self, uri): ...

    def normalizeUri(self, rdfTerm): ...

    def compute_qname(self, uri, generate=True): ...

    def bind(self, prefix, namespace, override=True, replace=False): ...

    def namespaces(self): ...

    def absolutize(self, uri, defrag=1): ...


def is_ncname(name): ...


XMLNS = ...  # type: Any


def split_uri(uri: Union[str, unicode]) -> Tuple[str, str]: ...
