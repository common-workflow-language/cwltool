from rdflib.namespace import DefinedNamespace as DefinedNamespace
from rdflib.namespace import Namespace as Namespace
from rdflib.term import URIRef as URIRef

class QB(DefinedNamespace):
    attribute: URIRef
    codeList: URIRef
    component: URIRef
    componentAttachment: URIRef
    componentProperty: URIRef
    componentRequired: URIRef
    concept: URIRef
    dataSet: URIRef
    dimension: URIRef
    hierarchyRoot: URIRef
    measure: URIRef
    measureDimension: URIRef
    measureType: URIRef
    observation: URIRef
    observationGroup: URIRef
    order: URIRef
    parentChildProperty: URIRef
    slice: URIRef
    sliceKey: URIRef
    sliceStructure: URIRef
    structure: URIRef
    Attachable: URIRef
    AttributeProperty: URIRef
    CodedProperty: URIRef
    ComponentProperty: URIRef
    ComponentSet: URIRef
    ComponentSpecification: URIRef
    DataSet: URIRef
    DataStructureDefinition: URIRef
    DimensionProperty: URIRef
    HierarchicalCodeList: URIRef
    MeasureProperty: URIRef
    Observation: URIRef
    ObservationGroup: URIRef
    Slice: URIRef
    SliceKey: URIRef
