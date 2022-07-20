from rdflib.namespace import DefinedNamespace as DefinedNamespace
from rdflib.namespace import Namespace as Namespace
from rdflib.term import URIRef as URIRef

class SSN(DefinedNamespace):
    Deployment: URIRef
    Input: URIRef
    Output: URIRef
    Property: URIRef
    Stimulus: URIRef
    System: URIRef
    wasOriginatedBy: URIRef
    deployedOnPlatform: URIRef
    deployedSystem: URIRef
    detects: URIRef
    forProperty: URIRef
    hasDeployment: URIRef
    hasInput: URIRef
    hasOutput: URIRef
    hasProperty: URIRef
    hasSubSystem: URIRef
    implementedBy: URIRef
    implements: URIRef
    inDeployment: URIRef
    isPropertyOf: URIRef
    isProxyFor: URIRef
