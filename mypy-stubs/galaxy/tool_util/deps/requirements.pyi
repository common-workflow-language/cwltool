from typing import Any, Dict, Iterable, List, Union

from _typeshed import Incomplete

DEFAULT_REQUIREMENT_TYPE: str
DEFAULT_REQUIREMENT_VERSION: Incomplete

class ToolRequirement:
    name: Incomplete
    type: Incomplete
    version: Incomplete
    specs: Incomplete
    def __init__(
        self,
        name: Incomplete | None = ...,
        type: Incomplete | None = ...,
        version: Incomplete | None = ...,
        specs: Incomplete | None = ...,
    ) -> None: ...
    def to_dict(self) -> Dict[str, str]: ...
    def copy(self) -> ToolRequirement: ...
    @staticmethod
    def from_dict(d: Dict[str, str]) -> "ToolRequirement": ...
    def __eq__(self, other: Any) -> bool: ...
    def __ne__(self, other: Any) -> bool: ...
    def __hash__(self) -> int: ...

class ToolRequirements:
    tool_requirements: Incomplete
    def __init__(
        self,
        tool_requirements: List[Union[ToolRequirement, Dict[str, str]]] | None = ...,
    ) -> None: ...
    @staticmethod
    def from_list(
        requirements: List[Union[ToolRequirement, Dict[str, str]]]
    ) -> "ToolRequirements": ...
    @property
    def resolvable(self) -> "ToolRequirements": ...
    @property
    def packages(self) -> "ToolRequirements": ...
    def to_list(self) -> List[Dict[str, str]]: ...
    def append(self, requirement: Union[ToolRequirement, Dict[str, str]]) -> None: ...
    def __eq__(self, other: Any) -> bool: ...
    def __ne__(self, other: Any) -> bool: ...
    def __iter__(self) -> Iterable[ToolRequirement]: ...
    def __getitem__(self, ii: int) -> ToolRequirement: ...
    def __len__(self) -> int: ...
    def __hash__(self) -> int: ...
    def to_dict(self) -> List[Dict[str, str]]: ...

DEFAULT_CONTAINER_TYPE: str
DEFAULT_CONTAINER_RESOLVE_DEPENDENCIES: bool
DEFAULT_CONTAINER_SHELL: str

class ContainerDescription:
    identifier: str | None
    type: str
    resolve_dependencies: bool
    shell: str
    explicit: bool
    def __init__(
        self,
        identifier: str | None = ...,
        type: str = ...,
        resolve_dependencies: bool = ...,
        shell: str = ...,
    ) -> None: ...
    def to_dict(self, *args: Any, **kwds: Any) -> Dict[str, str]: ...
    @staticmethod
    def from_dict(dict: Dict[str, str]) -> "ContainerDescription": ...

# def parse_requirements_from_dict(root_dict): ...
# def parse_requirements_from_xml(xml_root): ...
