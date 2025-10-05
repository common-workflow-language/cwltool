from typing import Optional

from ..recipe import Recipe
from .base import WriterBase as WriterBase

class SingularityWriter(WriterBase):
    name: str
    def __init__(self, recipe: dict[str, Recipe] | None = ...) -> None: ...
    def validate(self) -> None: ...
    def convert(self, runscript: str = ..., force: bool = ...) -> str: ...
