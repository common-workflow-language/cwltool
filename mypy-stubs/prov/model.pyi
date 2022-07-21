from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from _typeshed import Incomplete
from prov.constants import *
# from prov import Error as Error, serializers as serializers
from prov.identifier import Identifier as Identifier
from prov.identifier import Namespace as Namespace

logger: Incomplete

# def parse_xsd_datetime(value): ...

DATATYPE_PARSERS: Incomplete
XSD_DATATYPE_PARSERS: Incomplete

# def first(a_set): ...

class ProvRecord:
    FORMAL_ATTRIBUTES: Incomplete
    def __init__(
        self, bundle: str, identifier: str, attributes: Dict[str, str] | None = ...
    ) -> None: ...
    def __hash__(self) -> int: ...
    def copy(self) -> ProvRecord: ...
    def get_type(self) -> str: ...
    def get_asserted_types(self) -> Set[str]: ...
    def add_asserted_type(self, type_identifier: str) -> None: ...
    def get_attribute(self, attr_name: str) -> Set[str]: ...
    @property
    def identifier(self) -> str: ...
    @property
    def attributes(self) -> List[Tuple[str, str]]: ...
    @property
    def args(self) -> Tuple[str, ...]: ...
    @property
    def formal_attributes(self) -> Tuple[Tuple[str, str], ...]: ...
    @property
    def extra_attributes(self) -> Tuple[Tuple[str, str], ...]: ...
    @property
    def bundle(self) -> "ProvBundle": ...
    @property
    def label(self) -> str: ...
    @property
    def value(self) -> str: ...
    def add_attributes(self, attributes: Dict[str, str]) -> None: ...
    def __eq__(self, other: Any) -> bool: ...
    def get_provn(self) -> str: ...
    def is_element(self) -> bool: ...
    def is_relation(self) -> bool: ...

class ProvElement(ProvRecord):
    def __init__(
        self,
        bundle: "ProvBundle",
        identifier: str,
        attributes: Dict[str, str] | None = ...,
    ) -> None: ...
    def is_element(self) -> bool: ...

class ProvRelation(ProvRecord):
    def is_relation(self) -> bool: ...

class ProvEntity(ProvElement):
    def wasGeneratedBy(
        self,
        activity: str,
        time: datetime | str | None = ...,
        attributes: Dict[str, str] | List[Tuple[str, str]] | None = ...,
    ) -> ProvGeneration: ...
    def wasInvalidatedBy(
        self,
        activity: str,
        time: datetime | str | None = ...,
        attributes: Dict[str, str] | List[Tuple[str, str]] | None = ...,
    ) -> ProvInvalidation: ...
    def wasDerivedFrom(
        self,
        usedEntity: str,
        activity: str | None = ...,
        generation: Incomplete | None = ...,
        usage: Incomplete | None = ...,
        attributes: Incomplete | None = ...,
    ) -> ProvDerivation: ...
    def wasAttributedTo(
        self,
        agent: str,
        attributes: Dict[str, str] | List[Tuple[str, str]] | None = ...,
    ) -> ProvAttribution: ...
    def alternateOf(self, alternate2: str) -> ProvElement: ...
    def specializationOf(self, generalEntity: str) -> ProvSpecialization: ...
    def hadMember(self, entity: str) -> ProvMembership: ...

class ProvActivity(ProvElement):
    FORMAL_ATTRIBUTES: Incomplete
    def set_time(
        self, startTime: Incomplete | None = ..., endTime: Incomplete | None = ...
    ) -> None: ...
    def get_startTime(self): ...
    def get_endTime(self): ...
    def used(
        self, entity, time: Incomplete | None = ..., attributes: Incomplete | None = ...
    ): ...
    def wasInformedBy(self, informant, attributes: Incomplete | None = ...): ...
    def wasStartedBy(
        self,
        trigger,
        starter: Incomplete | None = ...,
        time: Incomplete | None = ...,
        attributes: Incomplete | None = ...,
    ): ...
    def wasEndedBy(
        self,
        trigger,
        ender: Incomplete | None = ...,
        time: Incomplete | None = ...,
        attributes: Incomplete | None = ...,
    ): ...
    def wasAssociatedWith(
        self, agent, plan: Incomplete | None = ..., attributes: Incomplete | None = ...
    ): ...

class ProvGeneration(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvUsage(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvCommunication(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvStart(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvEnd(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvInvalidation(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvDerivation(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvAgent(ProvElement):
    def actedOnBehalfOf(
        self,
        responsible,
        activity: Incomplete | None = ...,
        attributes: Incomplete | None = ...,
    ): ...

class ProvAttribution(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvAssociation(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvDelegation(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvInfluence(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvSpecialization(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvAlternate(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

class ProvMention(ProvSpecialization):
    FORMAL_ATTRIBUTES: Incomplete

class ProvMembership(ProvRelation):
    FORMAL_ATTRIBUTES: Incomplete

PROV_REC_CLS: Incomplete
DEFAULT_NAMESPACES: Incomplete

class NamespaceManager(dict):
    parent: Incomplete
    def __init__(
        self,
        namespaces: Incomplete | None = ...,
        default: Incomplete | None = ...,
        parent: Incomplete | None = ...,
    ) -> None: ...
    def get_namespace(self, uri): ...
    def get_registered_namespaces(self): ...
    def set_default_namespace(self, uri) -> None: ...
    def get_default_namespace(self): ...
    def add_namespace(self, namespace): ...
    def add_namespaces(self, namespaces) -> None: ...
    def valid_qualified_name(self, qname): ...
    def get_anonymous_identifier(self, local_prefix: str = ...): ...

class ProvBundle:
    def __init__(
        self,
        records: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        namespaces: Incomplete | None = ...,
        document: Incomplete | None = ...,
    ) -> None: ...
    @property
    def namespaces(self): ...
    @property
    def default_ns_uri(self): ...
    @property
    def document(self): ...
    @property
    def identifier(self): ...
    @property
    def records(self): ...
    def set_default_namespace(self, uri) -> None: ...
    def get_default_namespace(self): ...
    def add_namespace(self, namespace_or_prefix, uri: Incomplete | None = ...): ...
    def get_registered_namespaces(self): ...
    def valid_qualified_name(self, identifier): ...
    def get_records(self, class_or_type_or_tuple: Incomplete | None = ...): ...
    def get_record(self, identifier): ...
    def is_document(self): ...
    def is_bundle(self): ...
    def has_bundles(self): ...
    @property
    def bundles(self): ...
    def get_provn(self, _indent_level: int = ...): ...
    def __eq__(self, other): ...
    def __ne__(self, other): ...
    __hash__: Incomplete
    def unified(self): ...
    def update(self, other) -> None: ...
    def new_record(
        self,
        record_type,
        identifier,
        attributes: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def add_record(self, record): ...
    def entity(self, identifier, other_attributes: Incomplete | None = ...): ...
    def activity(
        self,
        identifier,
        startTime: Incomplete | None = ...,
        endTime: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def generation(
        self,
        entity,
        activity: Incomplete | None = ...,
        time: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def usage(
        self,
        activity,
        entity: Incomplete | None = ...,
        time: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def start(
        self,
        activity,
        trigger: Incomplete | None = ...,
        starter: Incomplete | None = ...,
        time: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def end(
        self,
        activity,
        trigger: Incomplete | None = ...,
        ender: Incomplete | None = ...,
        time: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def invalidation(
        self,
        entity,
        activity: Incomplete | None = ...,
        time: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def communication(
        self,
        informed,
        informant,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def agent(self, identifier, other_attributes: Incomplete | None = ...): ...
    def attribution(
        self,
        entity,
        agent,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def association(
        self,
        activity,
        agent: Incomplete | None = ...,
        plan: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def delegation(
        self,
        delegate,
        responsible,
        activity: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def influence(
        self,
        influencee,
        influencer,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def derivation(
        self,
        generatedEntity,
        usedEntity,
        activity: Incomplete | None = ...,
        generation: Incomplete | None = ...,
        usage: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def revision(
        self,
        generatedEntity,
        usedEntity,
        activity: Incomplete | None = ...,
        generation: Incomplete | None = ...,
        usage: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def quotation(
        self,
        generatedEntity,
        usedEntity,
        activity: Incomplete | None = ...,
        generation: Incomplete | None = ...,
        usage: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def primary_source(
        self,
        generatedEntity,
        usedEntity,
        activity: Incomplete | None = ...,
        generation: Incomplete | None = ...,
        usage: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
        other_attributes: Incomplete | None = ...,
    ): ...
    def specialization(self, specificEntity, generalEntity): ...
    def alternate(self, alternate1, alternate2): ...
    def mention(self, specificEntity, generalEntity, bundle): ...
    def collection(self, identifier, other_attributes: Incomplete | None = ...): ...
    def membership(self, collection, entity): ...
    def plot(
        self,
        filename: Incomplete | None = ...,
        show_nary: bool = ...,
        use_labels: bool = ...,
        show_element_attributes: bool = ...,
        show_relation_attributes: bool = ...,
    ) -> None: ...
    wasGeneratedBy: Incomplete
    used: Incomplete
    wasStartedBy: Incomplete
    wasEndedBy: Incomplete
    wasInvalidatedBy: Incomplete
    wasInformedBy: Incomplete
    wasAttributedTo: Incomplete
    wasAssociatedWith: Incomplete
    actedOnBehalfOf: Incomplete
    wasInfluencedBy: Incomplete
    wasDerivedFrom: Incomplete
    wasRevisionOf: Incomplete
    wasQuotedFrom: Incomplete
    hadPrimarySource: Incomplete
    alternateOf: Incomplete
    specializationOf: Incomplete
    mentionOf: Incomplete
    hadMember: Incomplete

class ProvDocument(ProvBundle):
    def __init__(
        self, records: Incomplete | None = ..., namespaces: Incomplete | None = ...
    ) -> None: ...
    def __eq__(self, other): ...
    def is_document(self): ...
    def is_bundle(self): ...
    def has_bundles(self): ...
    @property
    def bundles(self): ...
    def flattened(self): ...
    def unified(self): ...
    def update(self, other) -> None: ...
    def add_bundle(self, bundle, identifier: Incomplete | None = ...) -> None: ...
    def bundle(self, identifier): ...
    def serialize(
        self, destination: Incomplete | None = ..., format: str = ..., **args
    ): ...
    @staticmethod
    def deserialize(
        source: Incomplete | None = ...,
        content: Incomplete | None = ...,
        format: str = ...,
        **args
    ): ...

def sorted_attributes(element, attributes): ...
