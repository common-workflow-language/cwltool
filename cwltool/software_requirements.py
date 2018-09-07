"""This module handles resolution of SoftwareRequirement hints.

This is accomplished mainly by adapting cwltool internals to galaxy-lib's
concept of "dependencies". Despite the name, galaxy-lib is a light weight
library that can be used to map SoftwareRequirements in all sorts of ways -
Homebrew, Conda, custom scripts, environment modules. We'd be happy to find
ways to adapt new packages managers and such as well.
"""
from __future__ import absolute_import

import argparse  # pylint: disable=unused-import
import os
import string
from typing import Dict, List, MutableSequence, Optional

from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .builder import Builder, HasReqsHints
try:
    from galaxy.tools.deps.requirements import ToolRequirement, ToolRequirements
    from galaxy.tools import deps
except ImportError:
    ToolRequirement = None  # type: ignore
    ToolRequirements = None  # type: ignore
    deps = None  # type: ignore


SOFTWARE_REQUIREMENTS_ENABLED = deps is not None

COMMAND_WITH_DEPENDENCIES_TEMPLATE = string.Template("""#!/bin/bash
$handle_dependencies
python "run_job.py" "job.json"
""")


class DependenciesConfiguration(object):

    def __init__(self, args):
        # type: (argparse.Namespace) -> None
        conf_file = getattr(args, "beta_dependency_resolvers_configuration", None)
        tool_dependency_dir = getattr(args, "beta_dependencies_directory", None)
        conda_dependencies = getattr(args, "beta_conda_dependencies", None)
        if conf_file is not None and os.path.exists(conf_file):
            self.use_tool_dependencies = True
            if not tool_dependency_dir:
                tool_dependency_dir = os.path.abspath(os.path.dirname(conf_file))
            self.tool_dependency_dir = tool_dependency_dir
            self.dependency_resolvers_config_file = os.path.abspath(conf_file)
        elif conda_dependencies:
            if not tool_dependency_dir:
                tool_dependency_dir = os.path.abspath("./cwltool_deps")
            self.tool_dependency_dir = tool_dependency_dir
            self.use_tool_dependencies = True
            self.dependency_resolvers_config_file = None
        else:
            self.use_tool_dependencies = False

    @property
    def config_dict(self):
        return {
            'conda_auto_install': True,
            'conda_auto_init': True,
        }

    def build_job_script(self, builder, command):
        # type: (Builder, List[str]) -> Text
        ensure_galaxy_lib_available()
        tool_dependency_manager = deps.build_dependency_manager(self)  # type: deps.DependencyManager
        dependencies = get_dependencies(builder)
        handle_dependencies = ""  # str
        if dependencies:
            handle_dependencies = "\n".join(
                tool_dependency_manager.dependency_shell_commands(
                    dependencies, job_directory=builder.tmpdir))

        template_kwds = dict(handle_dependencies=handle_dependencies)  # type: Dict[str, str]
        job_script = COMMAND_WITH_DEPENDENCIES_TEMPLATE.substitute(template_kwds)
        return job_script


def get_dependencies(builder):  # type: (HasReqsHints) -> ToolRequirements
    (software_requirement, _) = builder.get_requirement("SoftwareRequirement")
    dependencies = []  # type: List[ToolRequirement]
    if software_requirement and software_requirement.get("packages"):
        packages = software_requirement.get("packages")
        for package in packages:
            version = package.get("version", None)
            if isinstance(version, MutableSequence):
                if version:
                    version = version[0]
                else:
                    version = None
            specs = [{"uri": s} for s in package.get("specs", [])]
            dependencies.append(ToolRequirement.from_dict(dict(
                name=package["package"].split("#")[-1],
                version=version,
                type="package",
                specs=specs,
            )))

    return ToolRequirements.from_list(dependencies)


def get_container_from_software_requirements(use_biocontainers, builder):
    # type: (bool, HasReqsHints) -> Optional[Text]
    if use_biocontainers:
        ensure_galaxy_lib_available()
        from galaxy.tools.deps.containers import ContainerRegistry, AppInfo, ToolInfo, DOCKER_CONTAINER_TYPE
        app_info = AppInfo(
            involucro_auto_init=True,
            enable_beta_mulled_containers=True,
            container_image_cache_path=".",
        )  # type: AppInfo
        container_registry = ContainerRegistry(app_info)  # type: ContainerRegistry
        requirements = get_dependencies(builder)
        tool_info = ToolInfo(requirements=requirements)  # type: ToolInfo
        container_description = container_registry.find_best_container_description([DOCKER_CONTAINER_TYPE], tool_info)  # type: ignore
        if container_description:
            return container_description.identifier

    return None


def ensure_galaxy_lib_available():
    # type: () -> None
    if not SOFTWARE_REQUIREMENTS_ENABLED:
        raise Exception("Optional Python library galaxy-lib not available, it is required for this configuration.")
