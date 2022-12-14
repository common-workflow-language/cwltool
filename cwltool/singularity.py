"""Support for executing Docker containers using the Singularity 2.x engine."""

import logging
import os
import os.path
import re
import shutil
import sys
from subprocess import check_call, check_output  # nosec
from typing import Callable, Dict, List, MutableMapping, Optional, Tuple, cast

from schema_salad.sourceline import SourceLine

from .builder import Builder
from .context import RuntimeContext
from .errors import WorkflowException
from .job import ContainerCommandLineJob
from .loghandler import _logger
from .pathmapper import MapperEnt, PathMapper
from .singularity_utils import singularity_supports_userns
from .utils import CWLObjectType, create_tmp_dir, ensure_non_writable, ensure_writable

# Cached version number of singularity
# This is a list containing major and minor versions as integer.
# (The number of minor version digits can vary among different distributions,
#  therefore we need a list here.)
_SINGULARITY_VERSION: Optional[List[int]] = None
# Cached flavor / distribution of singularity
# Can be singularity, singularity-ce or apptainer
_SINGULARITY_FLAVOR: str = ""


def get_version() -> Tuple[List[int], str]:
    """
    Parse the output of 'singularity --version' to determine the singularity flavor /
    distribution (singularity, singularity-ce or apptainer) and the singularity version.
    Both pieces of information will be cached.

    Returns
    -------
    A tuple containing:
    - A tuple with major and minor version numbers as integer.
    - A string with the name of the singularity flavor.
    """
    global _SINGULARITY_VERSION  # pylint: disable=global-statement
    global _SINGULARITY_FLAVOR  # pylint: disable=global-statement
    if _SINGULARITY_VERSION is None:
        version_output = check_output(  # nosec
            ["singularity", "--version"], universal_newlines=True
        ).strip()

        version_match = re.match(r"(.+) version ([0-9\.]+)", version_output)
        if version_match is None:
            raise RuntimeError("Output of 'singularity --version' not recognized.")

        version_string = version_match.group(2)
        _SINGULARITY_VERSION = [int(i) for i in version_string.split(".")]
        _SINGULARITY_FLAVOR = version_match.group(1)

        _logger.debug(
            f"Singularity version: {version_string}" " ({_SINGULARITY_FLAVOR}."
        )
    return (_SINGULARITY_VERSION, _SINGULARITY_FLAVOR)


def is_apptainer_1_or_newer() -> bool:
    """
    Check if apptainer singularity distribution is version 1.0 or higher.

    Apptainer v1.0.0 is compatible with SingularityCE 3.9.5.
    See: https://github.com/apptainer/apptainer/releases
    """
    v = get_version()
    if v[1] != "apptainer":
        return False
    return v[0][0] >= 1


def is_version_2_6() -> bool:
    """
    Check if this singularity version is exactly version 2.6.

    Also returns False if the flavor is not singularity or singularity-ce.
    """
    v = get_version()
    if v[1] != "singularity" and v[1] != "singularity-ce":
        return False
    return v[0][0] == 2 and v[0][1] == 6


def is_version_3_or_newer() -> bool:
    """Check if this version is singularity version 3 or newer or equivalent."""
    if is_apptainer_1_or_newer():
        return True  # this is equivalent to singularity-ce > 3.9.5
    v = get_version()
    return v[0][0] >= 3


def is_version_3_1_or_newer() -> bool:
    """Check if this version is singularity version 3.1 or newer or equivalent."""
    if is_apptainer_1_or_newer():
        return True  # this is equivalent to singularity-ce > 3.9.5
    v = get_version()
    return v[0][0] >= 4 or (v[0][0] == 3 and v[0][1] >= 1)


def is_version_3_4_or_newer() -> bool:
    """Detect if Singularity v3.4+ is available."""
    if is_apptainer_1_or_newer():
        return True  # this is equivalent to singularity-ce > 3.9.5
    v = get_version()
    return v[0][0] >= 4 or (v[0][0] == 3 and v[0][1] >= 4)


def _normalize_image_id(string: str) -> str:
    return string.replace("/", "_") + ".img"


def _normalize_sif_id(string: str) -> str:
    return string.replace("/", "_") + ".sif"


class SingularityCommandLineJob(ContainerCommandLineJob):
    def __init__(
        self,
        builder: Builder,
        joborder: CWLObjectType,
        make_path_mapper: Callable[..., PathMapper],
        requirements: List[CWLObjectType],
        hints: List[CWLObjectType],
        name: str,
    ) -> None:
        """Builder for invoking the Singularty software container engine."""
        super().__init__(builder, joborder, make_path_mapper, requirements, hints, name)

    @staticmethod
    def get_image(
        dockerRequirement: Dict[str, str],
        pull_image: bool,
        force_pull: bool = False,
    ) -> bool:
        """
        Acquire the software container image in the specified dockerRequirement.

        Uses Singularity and returns the success as a bool. Updates the
        provided dockerRequirement with the specific dockerImageId to the full
        path of the local image, if found. Likewise the
        dockerRequirement['dockerPull'] is updated to a docker:// URI if needed.
        """
        found = False

        candidates = []

        cache_folder = None
        debug = _logger.isEnabledFor(logging.DEBUG)

        if "CWL_SINGULARITY_CACHE" in os.environ:
            cache_folder = os.environ["CWL_SINGULARITY_CACHE"]
        elif is_version_2_6() and "SINGULARITY_PULLFOLDER" in os.environ:
            cache_folder = os.environ["SINGULARITY_PULLFOLDER"]

        if (
            "dockerImageId" not in dockerRequirement
            and "dockerPull" in dockerRequirement
        ):
            match = re.search(
                pattern=r"([a-z]*://)", string=dockerRequirement["dockerPull"]
            )
            img_name = _normalize_image_id(dockerRequirement["dockerPull"])
            candidates.append(img_name)
            if is_version_3_or_newer():
                sif_name = _normalize_sif_id(dockerRequirement["dockerPull"])
                candidates.append(sif_name)
                dockerRequirement["dockerImageId"] = sif_name
            else:
                dockerRequirement["dockerImageId"] = img_name
            if not match:
                dockerRequirement["dockerPull"] = (
                    "docker://" + dockerRequirement["dockerPull"]
                )
        elif "dockerImageId" in dockerRequirement:
            if os.path.isfile(dockerRequirement["dockerImageId"]):
                found = True
            candidates.append(dockerRequirement["dockerImageId"])
            candidates.append(_normalize_image_id(dockerRequirement["dockerImageId"]))
            if is_version_3_or_newer():
                candidates.append(_normalize_sif_id(dockerRequirement["dockerImageId"]))

        targets = [os.getcwd()]
        if "CWL_SINGULARITY_CACHE" in os.environ:
            targets.append(os.environ["CWL_SINGULARITY_CACHE"])
        if is_version_2_6() and "SINGULARITY_PULLFOLDER" in os.environ:
            targets.append(os.environ["SINGULARITY_PULLFOLDER"])
        for target in targets:
            for dirpath, _subdirs, files in os.walk(target):
                for entry in files:
                    if entry in candidates:
                        path = os.path.join(dirpath, entry)
                        if os.path.isfile(path):
                            _logger.info(
                                "Using local copy of Singularity image found in %s",
                                dirpath,
                            )
                            dockerRequirement["dockerImageId"] = path
                            found = True
        if (force_pull or not found) and pull_image:
            cmd = []  # type: List[str]
            if "dockerPull" in dockerRequirement:
                if cache_folder:
                    env = os.environ.copy()
                    if is_version_2_6():
                        env["SINGULARITY_PULLFOLDER"] = cache_folder
                        cmd = [
                            "singularity",
                            "pull",
                            "--force",
                            "--name",
                            dockerRequirement["dockerImageId"],
                            str(dockerRequirement["dockerPull"]),
                        ]
                    else:
                        cmd = [
                            "singularity",
                            "pull",
                            "--force",
                            "--name",
                            "{}/{}".format(
                                cache_folder, dockerRequirement["dockerImageId"]
                            ),
                            str(dockerRequirement["dockerPull"]),
                        ]

                    _logger.info(str(cmd))
                    check_call(cmd, env=env, stdout=sys.stderr)  # nosec
                    dockerRequirement["dockerImageId"] = "{}/{}".format(
                        cache_folder, dockerRequirement["dockerImageId"]
                    )
                    found = True
                else:
                    cmd = [
                        "singularity",
                        "pull",
                        "--force",
                        "--name",
                        str(dockerRequirement["dockerImageId"]),
                        str(dockerRequirement["dockerPull"]),
                    ]
                    _logger.info(str(cmd))
                    check_call(cmd, stdout=sys.stderr)  # nosec
                    found = True

            elif "dockerFile" in dockerRequirement:
                raise SourceLine(
                    dockerRequirement, "dockerFile", WorkflowException, debug
                ).makeError(
                    "dockerFile is not currently supported when using the "
                    "Singularity runtime for Docker containers."
                )
            elif "dockerLoad" in dockerRequirement:
                if is_version_3_1_or_newer():
                    if "dockerImageId" in dockerRequirement:
                        name = "{}.sif".format(dockerRequirement["dockerImageId"])
                    else:
                        name = "{}.sif".format(dockerRequirement["dockerLoad"])
                    cmd = [
                        "singularity",
                        "build",
                        name,
                        "docker-archive://{}".format(dockerRequirement["dockerLoad"]),
                    ]
                    _logger.info(str(cmd))
                    check_call(cmd, stdout=sys.stderr)  # nosec
                    found = True
                    dockerRequirement["dockerImageId"] = name
                else:
                    raise SourceLine(
                        dockerRequirement, "dockerLoad", WorkflowException, debug
                    ).makeError(
                        "dockerLoad is not currently supported when using the "
                        "Singularity runtime (version less than 3.1) for Docker containers."
                    )
            elif "dockerImport" in dockerRequirement:
                raise SourceLine(
                    dockerRequirement, "dockerImport", WorkflowException, debug
                ).makeError(
                    "dockerImport is not currently supported when using the "
                    "Singularity runtime for Docker containers."
                )

        return found

    def get_from_requirements(
        self,
        r: CWLObjectType,
        pull_image: bool,
        force_pull: bool,
        tmp_outdir_prefix: str,
    ) -> Optional[str]:
        """
        Return the filename of the Singularity image.

        (e.g. hello-world-latest.{img,sif}).
        """
        if not bool(shutil.which("singularity")):
            raise WorkflowException("singularity executable is not available")

        if not self.get_image(cast(Dict[str, str], r), pull_image, force_pull):
            raise WorkflowException(
                "Container image {} not found".format(r["dockerImageId"])
            )

        return os.path.abspath(cast(str, r["dockerImageId"]))

    @staticmethod
    def append_volume(
        runtime: List[str], source: str, target: str, writable: bool = False
    ) -> None:
        runtime.append("--bind")
        # Mounts are writable by default, so 'rw' is optional and not
        # supported (due to a bug) in some 3.6 series releases.
        vol = f"{source}:{target}"
        if not writable:
            vol += ":ro"
        runtime.append(vol)

    def add_file_or_directory_volume(
        self, runtime: List[str], volume: MapperEnt, host_outdir_tgt: Optional[str]
    ) -> None:
        if not volume.resolved.startswith("_:"):
            if host_outdir_tgt is not None and not is_version_3_4_or_newer():
                # workaround for lack of overlapping mounts in Singularity <3.4
                if volume.type == "File":
                    os.makedirs(os.path.dirname(host_outdir_tgt), exist_ok=True)
                    shutil.copy(volume.resolved, host_outdir_tgt)
                else:
                    shutil.copytree(volume.resolved, host_outdir_tgt)
                ensure_non_writable(host_outdir_tgt)
            else:
                self.append_volume(runtime, volume.resolved, volume.target)

    def add_writable_file_volume(
        self,
        runtime: List[str],
        volume: MapperEnt,
        host_outdir_tgt: Optional[str],
        tmpdir_prefix: str,
    ) -> None:
        if host_outdir_tgt is not None and not is_version_3_4_or_newer():
            # workaround for lack of overlapping mounts in Singularity <3.4
            if self.inplace_update:
                try:
                    os.link(os.path.realpath(volume.resolved), host_outdir_tgt)
                except os.error:
                    shutil.copy(volume.resolved, host_outdir_tgt)
            else:
                shutil.copy(volume.resolved, host_outdir_tgt)
            ensure_writable(host_outdir_tgt)
        elif self.inplace_update:
            self.append_volume(runtime, volume.resolved, volume.target, writable=True)
            ensure_writable(volume.resolved)
        else:
            if host_outdir_tgt:
                # shortcut, just copy to the output directory
                # which is already going to be mounted
                if not os.path.exists(os.path.dirname(host_outdir_tgt)):
                    os.makedirs(os.path.dirname(host_outdir_tgt))
                shutil.copy(volume.resolved, host_outdir_tgt)
                ensure_writable(host_outdir_tgt)
            else:
                file_copy = os.path.join(
                    create_tmp_dir(tmpdir_prefix),
                    os.path.basename(volume.resolved),
                )
                shutil.copy(volume.resolved, file_copy)
                self.append_volume(runtime, file_copy, volume.target, writable=True)
                ensure_writable(file_copy)

    def add_writable_directory_volume(
        self,
        runtime: List[str],
        volume: MapperEnt,
        host_outdir_tgt: Optional[str],
        tmpdir_prefix: str,
    ) -> None:
        if volume.resolved.startswith("_:"):
            # Synthetic directory that needs creating first
            if not host_outdir_tgt:
                new_dir = os.path.join(
                    create_tmp_dir(tmpdir_prefix),
                    os.path.basename(volume.target),
                )
                self.append_volume(runtime, new_dir, volume.target, writable=True)
                os.makedirs(new_dir)
                # ^^ Unlike Docker, Singularity won't create directories on demand
            elif not os.path.exists(host_outdir_tgt):
                os.makedirs(host_outdir_tgt)
        else:
            if host_outdir_tgt is not None and not is_version_3_4_or_newer():
                # workaround for lack of overlapping mounts in Singularity < 3.4
                shutil.copytree(volume.resolved, host_outdir_tgt)
                ensure_writable(host_outdir_tgt)
            else:
                if self.inplace_update:
                    self.append_volume(
                        runtime, volume.resolved, volume.target, writable=True
                    )
                else:
                    if not host_outdir_tgt:
                        tmpdir = create_tmp_dir(tmpdir_prefix)
                        new_dir = os.path.join(
                            tmpdir, os.path.basename(volume.resolved)
                        )
                        shutil.copytree(volume.resolved, new_dir)
                        self.append_volume(
                            runtime, new_dir, volume.target, writable=True
                        )
                    else:
                        shutil.copytree(volume.resolved, host_outdir_tgt)
                    ensure_writable(host_outdir_tgt or new_dir)

    def _required_env(self) -> Dict[str, str]:
        return {
            "TMPDIR": self.CONTAINER_TMPDIR,
            "HOME": self.builder.outdir,
        }

    def create_runtime(
        self, env: MutableMapping[str, str], runtime_context: RuntimeContext
    ) -> Tuple[List[str], Optional[str]]:
        """Return the Singularity runtime list of commands and options."""
        any_path_okay = self.builder.get_requirement("DockerRequirement")[1] or False
        runtime = [
            "singularity",
            "--quiet",
            "exec",
            "--contain",
            "--ipc",
            "--cleanenv",
        ]
        if singularity_supports_userns():
            runtime.append("--userns")
        else:
            runtime.append("--pid")

        container_HOME: Optional[str] = None
        if is_version_3_1_or_newer():
            # Remove HOME, as passed in a special way (restore it below)
            container_HOME = self.environment.pop("HOME")
            runtime.append("--home")
            runtime.append(
                "{}:{}".format(
                    os.path.realpath(self.outdir),
                    container_HOME,
                )
            )
        else:
            self.append_volume(
                runtime,
                os.path.realpath(self.outdir),
                self.environment["HOME"],
                writable=True,
            )

        self.append_volume(
            runtime, os.path.realpath(self.tmpdir), self.CONTAINER_TMPDIR, writable=True
        )

        self.add_volumes(
            self.pathmapper,
            runtime,
            any_path_okay=True,
            secret_store=runtime_context.secret_store,
            tmpdir_prefix=runtime_context.tmpdir_prefix,
        )
        if self.generatemapper is not None:
            self.add_volumes(
                self.generatemapper,
                runtime,
                any_path_okay=any_path_okay,
                secret_store=runtime_context.secret_store,
                tmpdir_prefix=runtime_context.tmpdir_prefix,
            )

        runtime.append("--pwd")
        runtime.append(self.builder.outdir)

        if self.networkaccess:
            if runtime_context.custom_net:
                runtime.extend(["--net", "--network", runtime_context.custom_net])
        else:
            runtime.extend(["--net", "--network", "none"])

        if self.builder.resources.get("cudaDeviceCount"):
            runtime.append("--nv")

        for name, value in self.environment.items():
            env[f"SINGULARITYENV_{name}"] = str(value)

        if container_HOME:
            # Restore HOME if we removed it above.
            self.environment["HOME"] = container_HOME
        return (runtime, None)
