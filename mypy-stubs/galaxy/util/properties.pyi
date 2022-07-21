from configparser import ConfigParser

from _typeshed import Incomplete

def find_config_file(
    names,
    exts: Incomplete | None = ...,
    dirs: Incomplete | None = ...,
    include_samples: bool = ...,
): ...
def load_app_properties(
    kwds: Incomplete | None = ...,
    ini_file: Incomplete | None = ...,
    ini_section: Incomplete | None = ...,
    config_file: Incomplete | None = ...,
    config_section: Incomplete | None = ...,
    config_prefix: str = ...,
): ...

class NicerConfigParser(ConfigParser):
    filename: Incomplete
    def __init__(self, filename, *args, **kw) -> None: ...
    read_file: Incomplete
    def defaults(self): ...

    class InterpolateWrapper:
        def __init__(self, original) -> None: ...
        def __getattr__(self, name): ...
        def before_get(self, parser, section, option, value, defaults): ...

running_from_source: Incomplete

def get_data_dir(properties): ...
