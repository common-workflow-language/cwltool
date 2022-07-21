from _typeshed import Incomplete
from typing import List, Optional, Union

class _ObjectType:
    name: Optional[str]
    egg_protocols: Optional[List[Union[str, List[str]]]]
    config_prefixes: Optional[List[Union[List[str], str]]]
    def __init__(self) -> None: ...
    def invoke(self, context): ...

class _App(_ObjectType):
    name: str
    egg_protocols: Incomplete
    config_prefixes: Incomplete
    def invoke(self, context): ...

class _Filter(_ObjectType):
    name: str
    egg_protocols: Incomplete
    config_prefixes: Incomplete
    def invoke(self, context): ...

class _Server(_ObjectType):
    name: str
    egg_protocols: Incomplete
    config_prefixes: Incomplete
    def invoke(self, context): ...

class _PipeLine(_ObjectType):
    name: str
    def invoke(self, context): ...

class _FilterApp(_ObjectType):
    name: str
    def invoke(self, context): ...

class _FilterWith(_App):
    name: str
    def invoke(self, context): ...

def loadapp(uri, name: Incomplete | None = ..., **kw): ...
def loadfilter(uri, name: Incomplete | None = ..., **kw): ...
def loadserver(uri, name: Incomplete | None = ..., **kw): ...
def appconfig(
    uri,
    name: Incomplete | None = ...,
    relative_to: Incomplete | None = ...,
    global_conf: Incomplete | None = ...,
): ...

class _Loader:
    def get_app(
        self, name: Incomplete | None = ..., global_conf: Incomplete | None = ...
    ): ...
    def get_filter(
        self, name: Incomplete | None = ..., global_conf: Incomplete | None = ...
    ): ...
    def get_server(
        self, name: Incomplete | None = ..., global_conf: Incomplete | None = ...
    ): ...
    def app_context(
        self, name: Incomplete | None = ..., global_conf: Incomplete | None = ...
    ): ...
    def filter_context(
        self, name: Incomplete | None = ..., global_conf: Incomplete | None = ...
    ): ...
    def server_context(
        self, name: Incomplete | None = ..., global_conf: Incomplete | None = ...
    ): ...
    def absolute_name(self, name): ...

class ConfigLoader(_Loader):
    filename: Incomplete
    parser: Incomplete
    def __init__(self, filename) -> None: ...
    def update_defaults(self, new_defaults, overwrite: bool = ...) -> None: ...
    def get_context(
        self,
        object_type,
        name: Incomplete | None = ...,
        global_conf: Incomplete | None = ...,
    ): ...
    def find_config_section(self, object_type, name: Incomplete | None = ...): ...

class EggLoader(_Loader):
    spec: Incomplete
    def __init__(self, spec) -> None: ...
    def get_context(
        self,
        object_type,
        name: Incomplete | None = ...,
        global_conf: Incomplete | None = ...,
    ): ...
    def find_egg_entry_point(self, object_type, name: Incomplete | None = ...): ...

class FuncLoader(_Loader):
    spec: Incomplete
    def __init__(self, spec) -> None: ...
    def get_context(
        self,
        object_type,
        name: Incomplete | None = ...,
        global_conf: Incomplete | None = ...,
    ): ...

class LoaderContext:
    object: Incomplete
    object_type: Incomplete
    protocol: Incomplete
    global_conf: Incomplete
    local_conf: Incomplete
    loader: Incomplete
    distribution: Incomplete
    entry_point_name: Incomplete
    def __init__(
        self,
        obj,
        object_type,
        protocol,
        global_conf,
        local_conf,
        loader,
        distribution: Incomplete | None = ...,
        entry_point_name: Incomplete | None = ...,
    ) -> None: ...
    def create(self): ...
    def config(self): ...

class AttrDict(dict): ...
