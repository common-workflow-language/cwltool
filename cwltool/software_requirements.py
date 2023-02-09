"""This module handles resolution of SoftwareRequirement hints.

This is accomplished mainly by adapting cwltool internals to galaxy-tool-util's
concept of "dependencies". Despite the name, galaxy-tool-util is a light weight
library that can be used to map SoftwareRequirements in all sorts of ways -
Homebrew, Conda, custom scripts, environment modules. We'd be happy to find
ways to adapt new packages managers and such as well.
"""

import argparse
import os
import string
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Union,
    cast,
)

from .utils import HasReqsHints

if TYPE_CHECKING:
    from .builder import Builder

try:
    from galaxy.tool_util import deps
    from galaxy.tool_util.deps.requirements import ToolRequirement, ToolRequirements
except ImportError:
    ToolRequirement = None  # type: ignore
    ToolRequirements = None  # type: ignore
    deps = None  # type: ignore


SOFTWARE_REQUIREMENTS_ENABLED = deps is not None

COMMAND_WITH_DEPENDENCIES_TEMPLATE = string.Template(
    """#!/bin/bash
cat > modify_environment.bash <<'EOF'
$handle_dependencies
# First try env -0
if ! env -0 > "output_environment.dat" 2> /dev/null; then
    # If that fails, use the python script.
    # In some circumstances (see PEP 538) this will the add LC_CTYPE env var.
    python3 "env_to_stdout.py" > "output_environment.dat"
fi
EOF
python3 "run_job.py" "job.json" "modify_environment.bash"
"""
)


class DependenciesConfiguration:
    """Dependency configuration class, for RuntimeContext.job_script_provider."""

    def __init__(self, args: argparse.Namespace) -> None:
        """Initialize."""
        conf_file = getattr(args, "beta_dependency_resolvers_configuration", None)
        tool_dependency_dir = getattr(args, "beta_dependencies_directory", None)
        conda_dependencies = getattr(args, "beta_conda_dependencies", None)
        if conf_file is not None and os.path.exists(conf_file):
            self.use_tool_dependencies = True
            if tool_dependency_dir is None:
                tool_dependency_dir = os.path.abspath(os.path.dirname(conf_file))
            self.tool_dependency_dir = tool_dependency_dir
            self.dependency_resolvers_config_file = os.path.abspath(conf_file)
        elif conda_dependencies is not None:
            if tool_dependency_dir is None:
                tool_dependency_dir = os.path.abspath("./cwltool_deps")
            self.tool_dependency_dir = tool_dependency_dir
            self.use_tool_dependencies = True
            self.dependency_resolvers_config_file = None
        else:
            self.use_tool_dependencies = False

    def build_job_script(self, builder: "Builder", command: List[str]) -> str:
        ensure_galaxy_lib_available()
        resolution_config_dict = {
            "use": self.use_tool_dependencies,
            "default_base_path": self.tool_dependency_dir,
        }
        app_config = {
            "conda_auto_install": True,
            "conda_auto_init": True,
        }
        tool_dependency_manager: "deps.DependencyManager" = deps.build_dependency_manager(
            app_config_dict=app_config,
            resolution_config_dict=resolution_config_dict,
            conf_file=self.dependency_resolvers_config_file,
        )
        dependencies = get_dependencies(builder)
        handle_dependencies = ""  # str
        if dependencies:
            handle_dependencies = "\n".join(
                tool_dependency_manager.dependency_shell_commands(
                    dependencies, job_directory=builder.tmpdir
                )
            )

        template_kwds: Dict[str, str] = dict(handle_dependencies=handle_dependencies)
        job_script = COMMAND_WITH_DEPENDENCIES_TEMPLATE.substitute(template_kwds)
        return job_script


def get_dependencies(builder: HasReqsHints) -> ToolRequirements:
    (software_requirement, _) = builder.get_requirement("SoftwareRequirement")
    dependencies: List["ToolRequirement"] = []
    if software_requirement and software_requirement.get("packages"):
        packages = cast(
            MutableSequence[MutableMapping[str, Union[str, MutableSequence[str]]]],
            software_requirement.get("packages"),
        )
        for package in packages:
            version = package.get("version", None)
            if isinstance(version, MutableSequence):
                if version:
                    version = version[0]
                else:
                    version = None
            specs = [{"uri": s} for s in package.get("specs", [])]
            dependencies.append(
                ToolRequirement.from_dict(
                    dict(
                        name=cast(str, package["package"]).split("#")[-1],
                        version=version,
                        type="package",
                        specs=specs,
                    )
                )
            )

    return ToolRequirements.from_list(dependencies)


def get_container_from_software_requirements(
    use_biocontainers: bool, builder: HasReqsHints, container_image_cache_path: Optional[str] = "."
) -> Optional[str]:
    if use_biocontainers:
        ensure_galaxy_lib_available()
        from galaxy.tool_util.deps.container_classes import DOCKER_CONTAINER_TYPE
        from galaxy.tool_util.deps.containers import ContainerRegistry
        from galaxy.tool_util.deps.dependencies import AppInfo, ToolInfo

        app_info: AppInfo = AppInfo(
            involucro_auto_init=True,
            enable_mulled_containers=True,
            container_image_cache_path=container_image_cache_path,
        )
        container_registry: ContainerRegistry = ContainerRegistry(app_info)
        requirements = get_dependencies(builder)
        tool_info: ToolInfo = ToolInfo(requirements=requirements)
        container_description = container_registry.find_best_container_description(
            [DOCKER_CONTAINER_TYPE], tool_info
        )
        if container_description:
            return cast(Optional[str], container_description.identifier)

    return None


def ensure_galaxy_lib_available() -> None:
    if not SOFTWARE_REQUIREMENTS_ENABLED:
        raise Exception(
            "Optional Python library galaxy-tool-util not available, it is required for this configuration."
        )
