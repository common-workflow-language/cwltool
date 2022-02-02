from rdflib.namespace import DefinedNamespace as DefinedNamespace
from rdflib.namespace import Namespace as Namespace
from rdflib.term import URIRef as URIRef

class DCAT(DefinedNamespace):
    accessURL: URIRef
    bbox: URIRef
    byteSize: URIRef
    centroid: URIRef
    compressFormat: URIRef
    contactPoint: URIRef
    dataset: URIRef
    distribution: URIRef
    downloadURL: URIRef
    endDate: URIRef
    keyword: URIRef
    landingPage: URIRef
    mediaType: URIRef
    packageFormat: URIRef
    record: URIRef
    startDate: URIRef
    theme: URIRef
    themeTaxonomy: URIRef
    Catalog: URIRef
    CatalogRecord: URIRef
    Dataset: URIRef
    Distribution: URIRef
    DataService: URIRef
    Relationship: URIRef
    Resource: URIRef
    Role: URIRef
    spatialResolutionInMeters: URIRef
    temporalResolution: URIRef
    accessService: URIRef
    catalog: URIRef
    endpointDescription: URIRef
    endpointURL: URIRef
    hadRole: URIRef
    qualifiedRelation: URIRef
    servesDataset: URIRef
    service: URIRef
