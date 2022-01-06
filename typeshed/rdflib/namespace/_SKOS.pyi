from rdflib.namespace import DefinedNamespace as DefinedNamespace
from rdflib.namespace import Namespace as Namespace
from rdflib.term import URIRef as URIRef

class SKOS(DefinedNamespace):
    altLabel: URIRef
    broadMatch: URIRef
    broader: URIRef
    broaderTransitive: URIRef
    changeNote: URIRef
    closeMatch: URIRef
    definition: URIRef
    editorialNote: URIRef
    exactMatch: URIRef
    example: URIRef
    hasTopConcept: URIRef
    hiddenLabel: URIRef
    historyNote: URIRef
    inScheme: URIRef
    mappingRelation: URIRef
    member: URIRef
    memberList: URIRef
    narrowMatch: URIRef
    narrower: URIRef
    narrowerTransitive: URIRef
    notation: URIRef
    note: URIRef
    prefLabel: URIRef
    related: URIRef
    relatedMatch: URIRef
    scopeNote: URIRef
    semanticRelation: URIRef
    topConceptOf: URIRef
    Collection: URIRef
    Concept: URIRef
    ConceptScheme: URIRef
    OrderedCollection: URIRef
