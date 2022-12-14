from rdflib.namespace import DefinedNamespace as DefinedNamespace
from rdflib.namespace import Namespace as Namespace
from rdflib.term import URIRef as URIRef

class VOID(DefinedNamespace):
    classPartition: URIRef
    classes: URIRef
    dataDump: URIRef
    distinctObjects: URIRef
    distinctSubjects: URIRef
    documents: URIRef
    entities: URIRef
    exampleResource: URIRef
    feature: URIRef
    inDataset: URIRef
    linkPredicate: URIRef
    objectsTarget: URIRef
    openSearchDescription: URIRef
    properties: URIRef
    property: URIRef
    propertyPartition: URIRef
    rootResource: URIRef
    sparqlEndpoint: URIRef
    subjectsTarget: URIRef
    subset: URIRef
    target: URIRef
    triples: URIRef
    uriLookupEndpoint: URIRef
    uriRegexPattern: URIRef
    uriSpace: URIRef
    vocabulary: URIRef
    Dataset: URIRef
    DatasetDescription: URIRef
    Linkset: URIRef
    TechnicalFeature: URIRef
