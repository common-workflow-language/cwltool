import abc

from ..recipe import Recipe

class ParserBase(metaclass=abc.ABCMeta):
    filename: str
    lines: list[str]
    args: dict[str, str]
    active_layer: str
    active_layer_num: int
    recipe: dict[str, Recipe]
    def __init__(self, filename: str, load: bool = ...) -> None: ...
    @abc.abstractmethod
    def parse(self) -> dict[str, Recipe]: ...
