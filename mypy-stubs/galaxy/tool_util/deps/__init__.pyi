from typing import Any, Dict, List, Optional

from .requirements import ToolRequirement as ToolRequirement
from .requirements import ToolRequirements as ToolRequirements

def build_dependency_manager(
    app_config_dict: Any, resolution_config_dict: Any, conf_file: Any
) -> DependencyManager: ...

class DependencyManager:
    default_base_path: str
    def __init__(
        self,
        default_base_path: str,
        conf_file: Optional[Any] = ...,
        app_config: Any = ...,
    ) -> None: ...
    def dependency_shell_commands(
        self, requirements: ToolRequirements, **kwds: Dict[str, str]
    ) -> List[str]: ...
