from datetime import datetime
from typing import IO, Any, Dict, Iterable, List, Set, Tuple

from _typeshed import Incomplete
from prov.constants import *

# from prov import Error as Error, serializers as serializers
from prov.identifier import Identifier, Namespace, QualifiedName

logger: Incomplete

# def parse_xsd_datetime(value): ...

DATATYPE_PARSERS: Incomplete
XSD_DATATYPE_PARSERS: Incomplete

# def first(a_set): ...

_attributes_type = Dict[str | Identifier, Any] | List[Tuple[str | Identifier, Any]]

class ProvRecord:
    FORMAL_ATTRIBUTES: Incomplete
    def __init__(
        self,
        bundle: str,
        identifier: Identifier | str,
        attributes: Dict[str, str] | None = ...,
    ) -> None: ...
    def __hash__(self) -> int: ...
    def copy(self) -> ProvRecord: ...
    def get_type(self) -> str: ...
    def get_asserted_types(self) -> Set[str]: ...
    def add_asserted_type(self, type_identifier: str | QualifiedName) -> None: ...
    def get_attribute(self, attr_name: str) -> Set[str]: ...
    @property
    def identifier(self) -> Identifier: ...
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
    def add_attributes(
        self,
        attributes: _attributes_type,
    ) -> None: ...
    def __eq__(self, other: Any) -> bool: ...
    def get_provn(self) -> str: ...
    def is_element(self) -> bool: ...
    def is_relation(self) -> bool: ...

class ProvElement(ProvRecord):
    def __init__(
        self,
        bundle: "ProvBundle",
        identifier: str,
        attributes: _attributes_type,
    ) -> None: ...
    def is_element(self) -> bool: ...

class ProvRelation(ProvRecord):
    def is_relation(self) -> bool: ...

class ProvEntity(ProvElement):
    def wasGeneratedBy(
        self,
        activity: str,
        time: datetime | str | None = ...,
        attributes: _attributes_type | None = None,
    ) -> ProvGeneration: ...
    def wasInvalidatedBy(
        self,
        activity: str,
        time: datetime | str | None = ...,
        attributes: _attributes_type | None = None,
    ) -> ProvInvalidation: ...
    def wasDerivedFrom(
        self,
        usedEntity: str,
        activity: str | None = ...,
        generation: Incomplete | None = ...,
        usage: Incomplete | None = ...,
        attributes: _attributes_type | None = None,
    ) -> ProvDerivation: ...
    def wasAttributedTo(
        self,
        agent: str,
        attributes: _attributes_type | None = None,
    ) -> ProvAttribution: ...
    def alternateOf(self, alternate2: str) -> ProvElement: ...
    def specializationOf(self, generalEntity: str) -> ProvSpecialization: ...
    def hadMember(self, entity: str) -> ProvMembership: ...

class ProvActivity(ProvElement):
    FORMAL_ATTRIBUTES: Incomplete
    def set_time(
        self, startTime: Incomplete | None = ..., endTime: Incomplete | None = ...
    ) -> None: ...
    def get_startTime(self) -> datetime: ...
    def get_endTime(self) -> datetime: ...
    def used(
        self,
        entity: str,
        time: datetime | str | None = ...,
        attributes: _attributes_type | None = None,
    ) -> ProvActivity: ...
    def wasInformedBy(
        self,
        informant: str,
        attributes: _attributes_type | None = None,
    ) -> ProvActivity: ...
    def wasStartedBy(
        self,
        trigger: str,
        starter: str | None = ...,
        time: datetime | str | None = ...,
        attributes: _attributes_type | None = None,
    ) -> ProvActivity: ...
    def wasEndedBy(
        self,
        trigger: str,
        ender: str | None = ...,
        time: datetime | str | None = ...,
        attributes: _attributes_type | None = None,
    ) -> ProvActivity: ...
    def wasAssociatedWith(
        self,
        agent: str,
        plan: str | None = ...,
        attributes: _attributes_type | None = None,
    ) -> ProvActivity: ...

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
        responsible: str,
        activity: str | None = ...,
        attributes: _attributes_type | None = ...,
    ) -> ProvAgent: ...

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

class ProvBundle:
    def __init__(
        self,
        records: Iterable[ProvRecord] | None = ...,
        identifier: str | None = ...,
        namespaces: Iterable[Namespace] | None = ...,
        document: ProvDocument | None = ...,
    ) -> None: ...
    @property
    def namespaces(self) -> Set[Namespace]: ...
    @property
    def default_ns_uri(self) -> str | None: ...
    @property
    def document(self) -> ProvDocument | None: ...
    @property
    def identifier(self) -> str | None: ...
    @property
    def records(self) -> List[ProvRecord]: ...
    def set_default_namespace(self, uri: Namespace) -> None: ...
    def get_default_namespace(self) -> Namespace: ...
    def add_namespace(
        self, namespace_or_prefix: Namespace | str, uri: str | None = ...
    ) -> Namespace: ...
    def get_registered_namespaces(self) -> Iterable[Namespace]: ...
    def valid_qualified_name(
        self, identifier: QualifiedName | Tuple[str, Identifier]
    ) -> QualifiedName | None: ...
    def get_records(
        self,
        class_or_type_or_tuple: type
        | type[int | str]
        | Tuple[type | type[int | str] | Tuple[Any, ...], ...]
        | None = ...,
    ) -> List[ProvRecord]: ...
    def get_record(
        self, identifier: Identifier | None
    ) -> ProvRecord | List[ProvRecord] | None: ...
    def is_document(self) -> bool: ...
    def is_bundle(self) -> bool: ...
    def has_bundles(self) -> bool: ...
    @property
    def bundles(self) -> Iterable[ProvBundle]: ...
    def get_provn(self, _indent_level: int = ...) -> str: ...
    def unified(self) -> ProvBundle: ...
    def update(self, other: ProvBundle) -> None: ...
    def new_record(
        self,
        record_type: PROV_REC_CLS,
        identifier: str,
        attributes: _attributes_type | None = None,
        other_attributes: _attributes_type | None = None,
    ) -> ProvRecord: ...
    def add_record(self, record: ProvRecord) -> ProvRecord: ...
    def entity(
        self,
        identifier: str | QualifiedName,
        other_attributes: _attributes_type | None = None,
    ) -> ProvEntity: ...
    def activity(
        self,
        identifier: str | QualifiedName,
        startTime: datetime | str | None = ...,
        endTime: datetime | str | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvActivity: ...
    def generation(
        self,
        entity: ProvEntity | str,
        activity: ProvActivity | str | None = ...,
        time: datetime | str | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvGeneration: ...
    def usage(
        self,
        activity: ProvActivity | str,
        entity: ProvEntity | str | None = ...,
        time: datetime | str | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvUsage: ...
    def start(
        self,
        activity: ProvActivity | ProvAgent | str,
        trigger: ProvEntity | None = ...,
        starter: ProvActivity | ProvAgent | str | None = ...,
        time: datetime | str | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvStart: ...
    def end(
        self,
        activity: ProvActivity | str,
        trigger: ProvEntity | None = ...,
        ender: ProvActivity | str | None = ...,
        time: datetime | str | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvEnd: ...
    def invalidation(
        self,
        entity: ProvEntity | str,
        activity: ProvActivity | str | None = ...,
        time: datetime | str | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvInvalidation: ...
    def communication(
        self,
        informed: ProvActivity | str,
        informant: ProvActivity | str,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvCommunication: ...
    def agent(
        self,
        identifier: Identifier | str,
        other_attributes: _attributes_type | None = None,
    ) -> ProvAgent: ...
    def attribution(
        self,
        entity: ProvEntity | str,
        agent: ProvAgent | str,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvAttribution: ...
    def association(
        self,
        activity: ProvActivity | str,
        agent: ProvAgent | str | None = ...,
        plan: ProvEntity | str | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvAssociation: ...
    def delegation(
        self,
        delegate: ProvAgent | str,
        responsible: ProvAgent | str,
        activity: ProvActivity | str | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvDelegation: ...
    def influence(
        self,
        influencee: ProvEntity | ProvActivity | ProvAgent | str,
        influencer: ProvEntity | ProvActivity | ProvAgent | str,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvInfluence: ...
    def derivation(
        self,
        generatedEntity: ProvEntity | str,
        usedEntity: ProvEntity | str,
        activity: ProvActivity | str | None = ...,
        generation: ProvActivity | str | None = ...,
        usage: Incomplete | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvDerivation: ...
    def revision(
        self,
        generatedEntity: ProvEntity | str,
        usedEntity: ProvEntity | str,
        activity: ProvActivity | str | None = ...,
        generation: ProvActivity | str | None = ...,
        usage: Incomplete | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvRecord: ...
    def quotation(
        self,
        generatedEntity: ProvEntity | str,
        usedEntity: ProvEntity | str,
        activity: ProvActivity | str | None = ...,
        generation: ProvActivity | str | None = ...,
        usage: Incomplete | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvRecord: ...
    def primary_source(
        self,
        generatedEntity: ProvEntity | str,
        usedEntity: ProvEntity | str,
        activity: ProvActivity | str | None = ...,
        generation: ProvActivity | str | None = ...,
        usage: Incomplete | None = ...,
        identifier: Identifier | None = ...,
        other_attributes: _attributes_type | None = None,
    ) -> ProvRecord: ...
    def specialization(
        self, specificEntity: ProvEntity | str, generalEntity: ProvEntity | str
    ) -> ProvRecord: ...
    def alternate(
        self, alternate1: ProvEntity | str, alternate2: ProvEntity | str
    ) -> ProvRecord: ...
    def mention(
        self,
        specificEntity: ProvEntity | str,
        generalEntity: ProvEntity | str,
        bundle: Incomplete,
    ) -> ProvRecord: ...
    def collection(
        self,
        identifier: str,
        other_attributes: _attributes_type | None,
    ) -> ProvRecord: ...
    def membership(
        self, collection: ProvRecord, entity: ProvEntity | str
    ) -> ProvRecord: ...
    def plot(
        self,
        filename: str | None = ...,
        show_nary: bool = ...,
        use_labels: bool = ...,
        show_element_attributes: bool = ...,
        show_relation_attributes: bool = ...,
    ) -> None: ...
    wasGeneratedBy = generation
    used = usage
    wasStartedBy = start
    wasEndedBy = end
    wasInvalidatedBy = invalidation
    wasInformedBy = communication
    wasAttributedTo = attribution
    wasAssociatedWith = association
    actedOnBehalfOf = delegation
    wasInfluencedBy = influence
    wasDerivedFrom = derivation
    wasRevisionOf = revision
    wasQuotedFrom = quotation
    hadPrimarySource = primary_source
    alternateOf = alternate
    specializationOf = specialization
    mentionOf = mention
    hadMember = membership

class ProvDocument(ProvBundle):
    def __init__(
        self,
        records: Iterable[ProvRecord] | None = ...,
        namespaces: Iterable[Namespace] | None = ...,
    ) -> None: ...
    def is_document(self) -> bool: ...
    def is_bundle(self) -> bool: ...
    def has_bundles(self) -> bool: ...
    @property
    def bundles(self) -> Iterable[ProvBundle]: ...
    def flattened(self) -> ProvDocument: ...
    def unified(self) -> ProvDocument: ...
    def update(self, other: ProvDocument | ProvBundle) -> None: ...
    def add_bundle(
        self, bundle: ProvBundle, identifier: Incomplete | None = ...
    ) -> None: ...
    def bundle(self, identifier: Identifier) -> ProvBundle: ...
    def serialize(
        self, destination: IO[Any] | None = ..., format: str = ..., **args: Any
    ) -> str | None: ...
    @staticmethod
    def deserialize(
        source: IO[Any] | str | None = ...,
        content: str | None = ...,
        format: str = ...,
        **args: Any
    ) -> ProvDocument: ...

def sorted_attributes(element: ProvElement, attributes: List[str]) -> List[str]: ...
