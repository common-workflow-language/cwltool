from _typeshed import Incomplete
from prov.model import (
    Identifier as Identifier,
    PROV_ACTIVITY as PROV_ACTIVITY,
    PROV_AGENT as PROV_AGENT,
    PROV_ALTERNATE as PROV_ALTERNATE,
    PROV_ASSOCIATION as PROV_ASSOCIATION,
    PROV_ATTRIBUTE_QNAMES as PROV_ATTRIBUTE_QNAMES,
    PROV_ATTRIBUTION as PROV_ATTRIBUTION,
    PROV_BUNDLE as PROV_BUNDLE,
    PROV_COMMUNICATION as PROV_COMMUNICATION,
    PROV_DELEGATION as PROV_DELEGATION,
    PROV_DERIVATION as PROV_DERIVATION,
    PROV_END as PROV_END,
    PROV_ENTITY as PROV_ENTITY,
    PROV_GENERATION as PROV_GENERATION,
    PROV_INFLUENCE as PROV_INFLUENCE,
    PROV_INVALIDATION as PROV_INVALIDATION,
    PROV_MEMBERSHIP as PROV_MEMBERSHIP,
    PROV_MENTION as PROV_MENTION,
    PROV_SPECIALIZATION as PROV_SPECIALIZATION,
    PROV_START as PROV_START,
    PROV_USAGE as PROV_USAGE,
    ProvException as ProvException,
    sorted_attributes as sorted_attributes,
)

DOT_PROV_STYLE: Incomplete
ANNOTATION_STYLE: Incomplete
ANNOTATION_LINK_STYLE: Incomplete
ANNOTATION_START_ROW: str
ANNOTATION_ROW_TEMPLATE: str
ANNOTATION_END_ROW: str

def htlm_link_if_uri(value): ...
def prov_to_dot(
    bundle,
    show_nary: bool = ...,
    use_labels: bool = ...,
    direction: str = ...,
    show_element_attributes: bool = ...,
    show_relation_attributes: bool = ...,
): ...
