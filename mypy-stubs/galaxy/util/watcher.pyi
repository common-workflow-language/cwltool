from _typeshed import Incomplete
from galaxy.util.hash_util import md5_hash_file as md5_hash_file
from watchdog.events import FileSystemEventHandler

can_watch: bool
FileSystemEventHandler = object
log: Incomplete

def get_observer_class(config_name, config_value, default, monitor_what_str): ...
def get_watcher(
    config,
    config_name,
    default: str = ...,
    monitor_what_str: Incomplete | None = ...,
    watcher_class: Incomplete | None = ...,
    event_handler_class: Incomplete | None = ...,
    **kwargs
): ...

class BaseWatcher:
    observer: Incomplete
    observer_class: Incomplete
    event_handler: Incomplete
    monitored_dirs: Incomplete
    def __init__(self, observer_class, even_handler_class, **kwargs) -> None: ...
    def start(self) -> None: ...
    def monitor(self, dir_path, recursive: bool = ...) -> None: ...
    def resume_watching(self) -> None: ...
    def shutdown(self) -> None: ...

class Watcher(BaseWatcher):
    path_hash: Incomplete
    file_callbacks: Incomplete
    dir_callbacks: Incomplete
    ignore_extensions: Incomplete
    require_extensions: Incomplete
    event_handler: Incomplete
    def __init__(self, observer_class, event_handler_class, **kwargs) -> None: ...
    def watch_file(self, file_path, callback: Incomplete | None = ...) -> None: ...
    def watch_directory(
        self,
        dir_path,
        callback: Incomplete | None = ...,
        recursive: bool = ...,
        ignore_extensions: Incomplete | None = ...,
        require_extensions: Incomplete | None = ...,
    ) -> None: ...

class EventHandler(FileSystemEventHandler):
    watcher: Incomplete
    def __init__(self, watcher) -> None: ...
    def on_any_event(self, event) -> None: ...

class NullWatcher:
    def start(self) -> None: ...
    def shutdown(self) -> None: ...
    def watch_file(self, *args, **kwargs) -> None: ...
    def watch_directory(self, *args, **kwargs) -> None: ...
