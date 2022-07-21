from _typeshed import Incomplete

SUFFIX_TO_BYTES: Incomplete

class ByteSize:
    value: Incomplete
    def __init__(self, value) -> None: ...
    def to_unit(self, unit: Incomplete | None = ..., as_string: bool = ...): ...

def parse_bytesize(value): ...
