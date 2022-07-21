# Stubs for galaxy.tools.parser.cwl (Python 3.4)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any

from .interface import PageSource as PageSource
from .interface import PagesSource as PagesSource
from .interface import ToolSource as ToolSource
from .interface import ToolStdioExitCode as ToolStdioExitCode
from .output_actions import ToolOutputActionGroup as ToolOutputActionGroup
from .output_objects import ToolOutput as ToolOutput
from .yaml import YamlInputSource as YamlInputSource

log = ...  # type: Any

class CwlToolSource(ToolSource):
    def __init__(self, tool_file, strict_cwl_validation: bool = ...) -> None: ...
    @property
    def tool_proxy(self): ...
    def parse_tool_type(self): ...
    def parse_id(self): ...
    def parse_name(self): ...
    def parse_command(self): ...
    def parse_environment_variables(self): ...
    def parse_edam_operations(self): ...
    def parse_edam_topics(self): ...
    def parse_help(self): ...
    def parse_sanitize(self): ...
    def parse_strict_shell(self): ...
    def parse_stdio(self): ...
    def parse_interpreter(self): ...
    def parse_version(self): ...
    def parse_description(self): ...
    def parse_input_pages(self): ...
    def parse_outputs(self, tool): ...
    def parse_requirements_and_containers(self): ...
    def parse_profile(self): ...

class CwlPageSource(PageSource):
    def __init__(self, tool_proxy) -> None: ...
    def parse_input_sources(self): ...
