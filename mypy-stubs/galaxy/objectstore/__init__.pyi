# Stubs for galaxy.objectstore (Python 3.4)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional

object_session = ...  # type: Any
NO_SESSION_ERROR_MESSAGE = ...  # type: str
log = ...  # type: Any

class ObjectStore:
    running = ...  # type: bool
    extra_dirs = ...  # type: Any
    config = ...  # type: Any
    check_old_style = ...  # type: Any
    def __init__(self, config, **kwargs) -> None: ...
    def shutdown(self): ...
    def exists(
        self,
        obj,
        base_dir: Optional[Any] = ...,
        dir_only: bool = ...,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
    ): ...
    def file_ready(
        self,
        obj,
        base_dir: Optional[Any] = ...,
        dir_only: bool = ...,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
        obj_dir: bool = ...,
    ): ...
    def create(
        self,
        obj,
        base_dir: Optional[Any] = ...,
        dir_only: bool = ...,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
        obj_dir: bool = ...,
    ): ...
    def empty(
        self,
        obj,
        base_dir: Optional[Any] = ...,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
        obj_dir: bool = ...,
    ): ...
    def size(
        self,
        obj,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
        obj_dir: bool = ...,
    ): ...
    def delete(
        self,
        obj,
        entire_dir: bool = ...,
        base_dir: Optional[Any] = ...,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
        obj_dir: bool = ...,
    ): ...
    def get_data(
        self,
        obj,
        start: int = ...,
        count: int = ...,
        base_dir: Optional[Any] = ...,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
        obj_dir: bool = ...,
    ): ...
    def get_filename(
        self,
        obj,
        base_dir: Optional[Any] = ...,
        dir_only: bool = ...,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
        obj_dir: bool = ...,
    ): ...
    def update_from_file(
        self,
        obj,
        base_dir: Optional[Any] = ...,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
        obj_dir: bool = ...,
        file_name: Optional[Any] = ...,
        create: bool = ...,
    ): ...
    def get_object_url(
        self,
        obj,
        extra_dir: Optional[Any] = ...,
        extra_dir_at_root: bool = ...,
        alt_name: Optional[Any] = ...,
        obj_dir: bool = ...,
    ): ...
    def get_store_usage_percent(self): ...

class DiskObjectStore(ObjectStore):
    file_path = ...  # type: Any
    def __init__(
        self,
        config,
        config_xml: Optional[Any] = ...,
        file_path: Optional[Any] = ...,
        extra_dirs: Optional[Any] = ...,
    ) -> None: ...
    def exists(self, obj, **kwargs): ...
    def create(self, obj, **kwargs): ...
    def empty(self, obj, **kwargs): ...
    def size(self, obj, **kwargs): ...
    def delete(self, obj, entire_dir: bool = ..., **kwargs): ...
    def get_data(self, obj, start: int = ..., count: int = ..., **kwargs): ...
    def get_filename(self, obj, **kwargs): ...
    def update_from_file(
        self, obj, file_name: Optional[Any] = ..., create: bool = ..., **kwargs
    ): ...
    def get_object_url(self, obj, **kwargs): ...
    def get_store_usage_percent(self): ...

class NestedObjectStore(ObjectStore):
    backends = ...  # type: Any
    def __init__(self, config, config_xml: Optional[Any] = ...) -> None: ...
    def shutdown(self): ...
    def exists(self, obj, **kwargs): ...
    def file_ready(self, obj, **kwargs): ...
    def create(self, obj, **kwargs): ...
    def empty(self, obj, **kwargs): ...
    def size(self, obj, **kwargs): ...
    def delete(self, obj, **kwargs): ...
    def get_data(self, obj, **kwargs): ...
    def get_filename(self, obj, **kwargs): ...
    def update_from_file(self, obj, **kwargs): ...
    def get_object_url(self, obj, **kwargs): ...

class DistributedObjectStore(NestedObjectStore):
    distributed_config = ...  # type: Any
    backends = ...  # type: Any
    weighted_backend_ids = ...  # type: Any
    original_weighted_backend_ids = ...  # type: Any
    max_percent_full = ...  # type: Any
    global_max_percent_full = ...  # type: float
    sleeper = ...  # type: Any
    filesystem_monitor_thread = ...  # type: Any
    def __init__(
        self, config, config_xml: Optional[Any] = ..., fsmon: bool = ...
    ) -> None: ...
    def shutdown(self): ...
    def create(self, obj, **kwargs): ...

class HierarchicalObjectStore(NestedObjectStore):
    backends = ...  # type: Any
    def __init__(
        self, config, config_xml: Optional[Any] = ..., fsmon: bool = ...
    ) -> None: ...
    def exists(self, obj, **kwargs): ...
    def create(self, obj, **kwargs): ...

def build_object_store_from_config(
    config, fsmon: bool = ..., config_xml: Optional[Any] = ...
): ...
def local_extra_dirs(func): ...
def convert_bytes(bytes): ...
