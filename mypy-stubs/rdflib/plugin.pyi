from typing import Any, Type, TypeVar

from rdflib.exceptions import Error

def register(name: str, kind: Any, module_path: str, class_name: str) -> None: ...

PluginT = TypeVar("PluginT")

def get(name: str, kind: Type[PluginT]) -> Type[PluginT]: ...
def plugins(name: Any | None = ..., kind: Any | None = ...) -> None: ...
