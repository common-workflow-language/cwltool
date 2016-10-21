# Stubs for galaxy.tools.deps.conda_util (Python 3.5)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any, Optional
import installable
from sys import platform as _platform

class CondaContext(installable.InstallableContext):
    installable_description = ...  # type: str
    condarc_override = ...  # type: Any
    conda_exec = ...  # type: Any
    debug = ...  # type: Any
    shell_exec = ...  # type: Any
    conda_prefix = ...  # type: Any
    ensure_channels = ...  # type: Any
    ensured_channels = ...  # type: bool
    def __init__(self, conda_prefix: Optional[Any] = ..., conda_exec: Optional[Any] = ..., shell_exec: Optional[Any] = ..., debug: bool = ..., ensure_channels: str = ..., condarc_override: Optional[Any] = ..., use_path_exec: Any = ...) -> None: ...
    def ensure_channels_configured(self): ...
    def conda_info(self): ...
    def is_conda_installed(self): ...
    def can_install_conda(self): ...
    def load_condarc(self): ...
    def save_condarc(self, conf): ...
    @property
    def condarc(self): ...
    def command(self, operation, args): ...
    def exec_command(self, operation, args): ...
    def exec_create(self, args): ...
    def exec_remove(self, args): ...
    def exec_install(self, args): ...
    def export_list(self, name, path): ...
    def env_path(self, env_name): ...
    @property
    def envs_path(self): ...
    def has_env(self, env_name): ...
    @property
    def deactivate(self): ...
    @property
    def activate(self): ...
    def is_installed(self): ...
    def can_install(self): ...
    @property
    def parent_path(self): ...

class CondaTarget:
    package = ...  # type: Any
    version = ...  # type: Any
    channel = ...  # type: Any
    def __init__(self, package, version: Optional[Any] = ..., channel: Optional[Any] = ...) -> None: ...
    @property
    def package_specifier(self): ...
    @property
    def install_environment(self): ...
    def __hash__(self): ...
    def __eq__(self, other): ...
    def __ne__(self, other): ...

def install_conda(conda_context: Optional[Any] = ...): ...
def install_conda_target(conda_target, conda_context: Optional[Any] = ...): ...
def requirements_to_conda_targets(requirements, conda_context: Optional[Any] = ...): ...
