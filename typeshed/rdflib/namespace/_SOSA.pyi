from rdflib.namespace import DefinedNamespace as DefinedNamespace
from rdflib.namespace import Namespace as Namespace
from rdflib.term import URIRef as URIRef

class SOSA(DefinedNamespace):
    ActuatableProperty: URIRef
    Actuation: URIRef
    Actuator: URIRef
    FeatureOfInterest: URIRef
    ObservableProperty: URIRef
    Observation: URIRef
    Platform: URIRef
    Procedure: URIRef
    Result: URIRef
    Sample: URIRef
    Sampler: URIRef
    Sampling: URIRef
    Sensor: URIRef
    hasSimpleResult: URIRef
    resultTime: URIRef
    actsOnProperty: URIRef
    hasFeatureOfInterest: URIRef
    hasResult: URIRef
    hasSample: URIRef
    hosts: URIRef
    isActedOnBy: URIRef
    isFeatureOfInterestOf: URIRef
    isHostedBy: URIRef
    isObservedBy: URIRef
    isResultOf: URIRef
    isSampleOf: URIRef
    madeActuation: URIRef
    madeByActuator: URIRef
    madeBySampler: URIRef
    madeBySensor: URIRef
    madeObservation: URIRef
    madeSampling: URIRef
    observedProperty: URIRef
    observes: URIRef
    phenomenonTime: URIRef
    usedProcedure: URIRef
