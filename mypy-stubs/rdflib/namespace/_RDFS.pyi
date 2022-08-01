from rdflib.namespace import DefinedNamespace as DefinedNamespace
from rdflib.namespace import Namespace as Namespace
from rdflib.term import URIRef as URIRef

class RDFS(DefinedNamespace):
    comment: URIRef
    domain: URIRef
    isDefinedBy: URIRef
    label: URIRef
    member: URIRef
    range: URIRef
    seeAlso: URIRef
    subClassOf: URIRef
    subPropertyOf: URIRef
    Class: URIRef
    Container: URIRef
    ContainerMembershipProperty: URIRef
    Datatype: URIRef
    Literal: URIRef
    Resource: URIRef
