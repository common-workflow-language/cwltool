from typing import Any, Type, TypeVar

from rdflib.exceptions import Error

class PluginException(Error): ...

class Plugin:
    name: Any
    kind: Any
    module_path: Any
    class_name: Any
    def __init__(self, name, kind, module_path, class_name) -> None: ...
    def getClass(self): ...

class PKGPlugin(Plugin):
    name: Any
    kind: Any
    ep: Any
    def __init__(self, name, kind, ep) -> None: ...
    def getClass(self): ...

def register(name: str, kind, module_path, class_name): ...

PluginT = TypeVar("PluginT")

def get(name: str, kind: Type[PluginT]) -> Type[PluginT]: ...
def plugins(name: Any | None = ..., kind: Any | None = ...) -> None: ...
