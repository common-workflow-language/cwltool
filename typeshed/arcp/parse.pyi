from urllib.parse import ParseResult
from typing import Any
from uuid import NAMESPACE_URL as NAMESPACE_URL

SCHEME: str

def is_arcp_uri(uri: Any): ...
def parse_arcp(uri: Any): ...
def urlparse(uri: Any): ...

class ARCPParseResult(ParseResult):
    def __init__(self, *args: Any) -> None: ...
    @property
    def prefix(self): ...
    @property
    def name(self): ...
    @property
    def uuid(self): ...
    @property
    def ni(self): ...
    def ni_uri(self, authority: str = ...): ...
    def nih_uri(self): ...
    def ni_well_known(self, base: str = ...): ...
    @property
    def hash(self): ...
