from _typeshed import Incomplete
from prov.model import PROV_ACTIVITY as PROV_ACTIVITY
from prov.model import PROV_AGENT as PROV_AGENT
from prov.model import PROV_ALTERNATE as PROV_ALTERNATE
from prov.model import PROV_ASSOCIATION as PROV_ASSOCIATION
from prov.model import PROV_ATTRIBUTE_QNAMES as PROV_ATTRIBUTE_QNAMES
from prov.model import PROV_ATTRIBUTION as PROV_ATTRIBUTION
from prov.model import PROV_BUNDLE as PROV_BUNDLE
from prov.model import PROV_COMMUNICATION as PROV_COMMUNICATION
from prov.model import PROV_DELEGATION as PROV_DELEGATION
from prov.model import PROV_DERIVATION as PROV_DERIVATION
from prov.model import PROV_END as PROV_END
from prov.model import PROV_ENTITY as PROV_ENTITY
from prov.model import PROV_GENERATION as PROV_GENERATION
from prov.model import PROV_INFLUENCE as PROV_INFLUENCE
from prov.model import PROV_INVALIDATION as PROV_INVALIDATION
from prov.model import PROV_MEMBERSHIP as PROV_MEMBERSHIP
from prov.model import PROV_MENTION as PROV_MENTION
from prov.model import PROV_SPECIALIZATION as PROV_SPECIALIZATION
from prov.model import PROV_START as PROV_START
from prov.model import PROV_USAGE as PROV_USAGE
from prov.model import Identifier as Identifier
from prov.model import ProvException as ProvException
from prov.model import sorted_attributes as sorted_attributes

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
