from rdflib.namespace import DefinedNamespace as DefinedNamespace
from rdflib.namespace import Namespace as Namespace
from rdflib.term import URIRef as URIRef

class DC(DefinedNamespace):
    contributor: URIRef
    coverage: URIRef
    creator: URIRef
    date: URIRef
    description: URIRef
    format: URIRef
    identifier: URIRef
    language: URIRef
    publisher: URIRef
    relation: URIRef
    rights: URIRef
    source: URIRef
    subject: URIRef
    title: URIRef
    type: URIRef
