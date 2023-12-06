from ..recipe import Recipe
from .base import ParserBase as ParserBase

class DockerParser(ParserBase):
    name: str
    def __init__(self, filename: str = ..., load: bool = ...) -> None: ...
    def parse(self) -> dict[str, Recipe]: ...
