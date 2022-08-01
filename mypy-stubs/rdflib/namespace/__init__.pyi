from typing import Any, Tuple

from rdflib.term import URIRef

__all__ = [
    "split_uri",
    "Namespace",
    "ClosedNamespace",
    "RDF",
    "RDFS",
    "CSVW",
    "DC",
    "DCAT",
    "DCTERMS",
    "DOAP",
    "FOAF",
    "ODRL2",
    "ORG",
    "OWL",
    "PROF",
    "PROV",
    "QB",
    "SDO",
    "SH",
    "SKOS",
    "SOSA",
    "SSN",
    "TIME",
    "VOID",
    "XSD",
    "OWL",
]

class Namespace(str):
    @property
    def title(self) -> URIRef: ...
    def term(self, name: Any) -> URIRef: ...
    def __getitem__(self, key: Any) -> URIRef: ...
    def __getattr__(self, name: str) -> URIRef: ...

class URIPattern(str):
    def format(self, *args: Any, **kwargs: Any) -> str: ...

class DefinedNamespaceMeta(type):
    def __getitem__(cls, name: Any, default: Any | None = ...) -> URIRef: ...
    def __getattr__(cls, name: Any) -> URIRef: ...
    def __contains__(cls, item: Any) -> bool: ...

class DefinedNamespace(metaclass=DefinedNamespaceMeta):
    def __init__(self) -> None: ...

class ClosedNamespace(Namespace):
    def __new__(cls, uri: Any, terms: Any) -> ClosedNamespace: ...
    @property
    def uri(self) -> str: ...

NAME_START_CATEGORIES = ["Ll", "Lu", "Lo", "Lt", "Nl"]
SPLIT_START_CATEGORIES = NAME_START_CATEGORIES + ["Nd"]

XMLNS = "http://www.w3.org/XML/1998/namespace"

def split_uri(uri: Any, split_start: Any = ...) -> Tuple[str, str]: ...

from rdflib.namespace._CSVW import CSVW
from rdflib.namespace._DC import DC
from rdflib.namespace._DCAT import DCAT
from rdflib.namespace._DCTERMS import DCTERMS
from rdflib.namespace._DOAP import DOAP
from rdflib.namespace._FOAF import FOAF
from rdflib.namespace._ODRL2 import ODRL2
from rdflib.namespace._ORG import ORG
from rdflib.namespace._OWL import OWL
from rdflib.namespace._PROF import PROF
from rdflib.namespace._PROV import PROV
from rdflib.namespace._QB import QB
from rdflib.namespace._RDF import RDF
from rdflib.namespace._RDFS import RDFS
from rdflib.namespace._SDO import SDO
from rdflib.namespace._SH import SH
from rdflib.namespace._SKOS import SKOS
from rdflib.namespace._SOSA import SOSA
from rdflib.namespace._SSN import SSN
from rdflib.namespace._TIME import TIME
from rdflib.namespace._VOID import VOID
from rdflib.namespace._XSD import XSD
