from .sleeper import Sleeper as Sleeper
from .web_compat import register_postfork_function as register_postfork_function
from _typeshed import Incomplete

log: Incomplete
DEFAULT_MONITOR_THREAD_JOIN_TIMEOUT: int

class Monitors:
    def start_monitoring(self) -> None: ...
    monitor_running: bool
    def stop_monitoring(self) -> None: ...
    def shutdown_monitor(self) -> None: ...
