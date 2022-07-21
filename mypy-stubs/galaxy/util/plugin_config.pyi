from typing import NamedTuple

from _typeshed import Incomplete
from galaxy.util.submodules import import_submodules as import_submodules

class PluginConfigSource(NamedTuple):
    type: Incomplete
    source: Incomplete

def plugins_dict(module, plugin_type_identifier): ...
def load_plugins(
    plugins_dict,
    plugin_source,
    extra_kwds: Incomplete | None = ...,
    plugin_type_keys=...,
    dict_to_list_key: Incomplete | None = ...,
): ...
def plugin_source_from_path(path): ...
def plugin_source_from_dict(as_dict): ...
