from collections.abc import Generator

from _typeshed import Incomplete
from prov.constants import PROV as PROV
from prov.constants import PROV_ACTIVITY as PROV_ACTIVITY
from prov.constants import PROV_ALTERNATE as PROV_ALTERNATE
from prov.constants import PROV_ATTR_ENDER as PROV_ATTR_ENDER
from prov.constants import PROV_ATTR_ENDTIME as PROV_ATTR_ENDTIME
from prov.constants import PROV_ATTR_INFORMANT as PROV_ATTR_INFORMANT
from prov.constants import PROV_ATTR_RESPONSIBLE as PROV_ATTR_RESPONSIBLE
from prov.constants import PROV_ATTR_STARTER as PROV_ATTR_STARTER
from prov.constants import PROV_ATTR_STARTTIME as PROV_ATTR_STARTTIME
from prov.constants import PROV_ATTR_TIME as PROV_ATTR_TIME
from prov.constants import PROV_ATTR_TRIGGER as PROV_ATTR_TRIGGER
from prov.constants import PROV_ATTR_USED_ENTITY as PROV_ATTR_USED_ENTITY
from prov.constants import PROV_BASE_CLS as PROV_BASE_CLS
from prov.constants import PROV_COMMUNICATION as PROV_COMMUNICATION
from prov.constants import PROV_DELEGATION as PROV_DELEGATION
from prov.constants import PROV_DERIVATION as PROV_DERIVATION
from prov.constants import PROV_END as PROV_END
from prov.constants import PROV_GENERATION as PROV_GENERATION
from prov.constants import PROV_ID_ATTRIBUTES_MAP as PROV_ID_ATTRIBUTES_MAP
from prov.constants import PROV_INVALIDATION as PROV_INVALIDATION
from prov.constants import PROV_LOCATION as PROV_LOCATION
from prov.constants import PROV_MENTION as PROV_MENTION
from prov.constants import PROV_N_MAP as PROV_N_MAP
from prov.constants import PROV_ROLE as PROV_ROLE
from prov.constants import PROV_START as PROV_START
from prov.constants import PROV_USAGE as PROV_USAGE
from prov.constants import XSD_QNAME as XSD_QNAME
from prov.serializers import Error as Error
from prov.serializers import Serializer as Serializer

class ProvRDFException(Error): ...

class AnonymousIDGenerator:
    def __init__(self) -> None: ...
    def get_anon_id(self, obj, local_prefix: str = ...): ...

LITERAL_XSDTYPE_MAP: Incomplete

def attr2rdf(attr): ...
def valid_qualified_name(bundle, value, xsd_qname: bool = ...): ...

class ProvRDFSerializer(Serializer):
    def serialize(
        self, stream: Incomplete | None = ..., rdf_format: str = ..., **kwargs
    ) -> None: ...
    document: Incomplete
    def deserialize(self, stream, rdf_format: str = ..., **kwargs): ...
    def valid_identifier(self, value): ...
    def encode_rdf_representation(self, value): ...
    def decode_rdf_representation(self, literal, graph): ...
    def encode_document(self, document): ...
    def encode_container(
        self,
        bundle,
        container: Incomplete | None = ...,
        identifier: Incomplete | None = ...,
    ): ...
    def decode_document(self, content, document) -> None: ...
    def decode_container(self, graph, bundle) -> None: ...

def walk(
    children, level: int = ..., path: Incomplete | None = ..., usename: bool = ...
) -> Generator[Incomplete, None, None]: ...
def literal_rdf_representation(literal): ...
