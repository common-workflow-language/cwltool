from _typeshed import Incomplete
from prov.serializers import Serializer as Serializer

logger: Incomplete

class ProvNSerializer(Serializer):
    def serialize(self, stream, **kwargs) -> None: ...
    def deserialize(self, stream, **kwargs) -> None: ...
