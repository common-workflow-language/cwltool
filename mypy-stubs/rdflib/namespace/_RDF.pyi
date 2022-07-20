from rdflib.namespace import DefinedNamespace as DefinedNamespace
from rdflib.namespace import Namespace as Namespace
from rdflib.term import URIRef as URIRef

class RDF(DefinedNamespace):
    nil: URIRef
    direction: URIRef
    first: URIRef
    language: URIRef
    object: URIRef
    predicate: URIRef
    rest: URIRef
    subject: URIRef
    type: URIRef
    value: URIRef
    Alt: URIRef
    Bag: URIRef
    CompoundLiteral: URIRef
    List: URIRef
    Property: URIRef
    Seq: URIRef
    Statement: URIRef
    HTML: URIRef
    JSON: URIRef
    PlainLiteral: URIRef
    XMLLiteral: URIRef
    langString: URIRef
