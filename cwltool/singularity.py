"""Support for executing Docker format containers using Singularity {2,3}.x or Apptainer 1.x."""

import copy
import hashlib
import json
import logging
import os
import os.path
import re
import shutil
import sys
import threading
from collections.abc import Callable, MutableMapping
from subprocess import check_call, check_output, run  # nosec
from typing import cast

from mypy_extensions import mypyc_attr
from packaging.version import Version
from schema_salad.sourceline import SourceLine
from schema_salad.utils import json_dumps
from spython.main import Client
from spython.main.parse.parsers.docker import DockerParser
from spython.main.parse.writers.singularity import SingularityWriter

from .builder import Builder
from .context import RuntimeContext
from .docker import DockerCommandLineJob
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
_SINGULARITY_VERSION: Version | None = None
# Cached flavor / distribution of singularity
# Can be singularity, singularity-ce or apptainer
_SINGULARITY_FLAVOR: str = ""


_IMAGES: dict[str, str] = {}
_IMAGES_LOCK = threading.Lock()


def get_version() -> tuple[Version, str]:
    """
    Parse the output of 'singularity --version' to determine the flavor and version.

    Both pieces of information will be cached.

    :returns: A tuple containing:
              - A parsed Version object.
              - A string with the name of the singularity flavor.
    """
    global _SINGULARITY_VERSION  # pylint: disable=global-statement
    global _SINGULARITY_FLAVOR  # pylint: disable=global-statement
    if _SINGULARITY_VERSION is None:
        version_output = check_output(["singularity", "--version"], text=True).strip()  # nosec

        version_match = re.match(r"(.+) version ([0-9\.]+)", version_output)
        if version_match is None:
            raise RuntimeError("Output of 'singularity --version' not recognized.")

        version_string = version_match.group(2)
        _SINGULARITY_VERSION = Version(version_string)
        _SINGULARITY_FLAVOR = version_match.group(1)

        _logger.debug(f"Singularity version: {version_string}" " ({_SINGULARITY_FLAVOR}.")
    return (_SINGULARITY_VERSION, _SINGULARITY_FLAVOR)


def is_apptainer_1_or_newer() -> bool:
    """
    Check if apptainer singularity distribution is version 1.0 or higher.

    Apptainer v1.0.0 is compatible with SingularityCE 3.9.5.
    See: https://github.com/apptainer/apptainer/releases
    """
    version, flavor = get_version()
    if flavor != "apptainer":
        return False
    return version >= Version("1")


def is_apptainer_1_1_or_newer() -> bool:
    """Check if apptainer singularity distribution is version 1.1 or higher."""
    version, flavor = get_version()
    if flavor != "apptainer":
        return False
    return version >= Version("1.1")


def is_version_2_6() -> bool:
    """
    Check if this singularity version is exactly version 2.6.

    Also returns False if the flavor is not singularity or singularity-ce.
    """
    version, flavor = get_version()
    if flavor not in ("singularity", "singularity-ce"):
        return False
    return version >= Version("2.6") and version < Version("2.7")


def is_version_3_or_newer() -> bool:
    """Check if this version is singularity version 3 or newer or equivalent."""
    if is_apptainer_1_or_newer():
        return True  # this is equivalent to singularity-ce > 3.9.5
    version, flavor = get_version()
    if flavor == "apptainer":
        return False
    return version >= Version("3")


def is_version_3_1_or_newer() -> bool:
    """Check if this version is singularity version 3.1 or newer or equivalent."""
    if is_apptainer_1_or_newer():
        return True  # this is equivalent to singularity-ce > 3.9.5
    version, flavor = get_version()
    if flavor == "apptainer":
        return False
    return version >= Version("3.1")


def is_version_3_4_or_newer() -> bool:
    """Detect if Singularity v3.4+ is available."""
    if is_apptainer_1_or_newer():
        return True  # this is equivalent to singularity-ce > 3.9.5
    version, flavor = get_version()
    if flavor == "apptainer":
        return False
    return version >= Version("3.4")


def is_version_3_9_or_newer() -> bool:
    """Detect if Singularity v3.9+ is available."""
    if is_apptainer_1_or_newer():
        return True  # this is equivalent to singularity-ce > 3.9.5
    version, flavor = get_version()
    if flavor == "apptainer":
        return False
    return version >= Version("3.9")


def is_version_3_10_or_newer() -> bool:
    """Detect if Singularity v3.10+ is available."""
    version, flavor = get_version()
    if flavor not in ("singularity", "singularity-ce"):
        return False
    return version >= Version("3.10")


def _normalize_image_id(string: str) -> str:
    if ":" not in string:
        string += "_latest"
    return string.replace("/", "_") + ".img"


def _normalize_sif_id(string: str) -> str:
    if ":" not in string:
        string += "_latest"
    return string.replace("/", "_") + ".sif"


@mypyc_attr(allow_interpreted_subclasses=True)
def _inspect_singularity_sandbox_image(path: str) -> bool:
    """Inspect singularity sandbox image to be sure it is not an empty directory."""
    cmd = [
        "singularity",
        "inspect",
        "--json",
        path,
    ]
    try:
        result = run(cmd, capture_output=True, text=True)  # nosec
    except Exception:
        return False

    if result.returncode == 0:
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False
        if output.get("data", {}).get("attributes", {}):
            return True
    return False


class SingularityCommandLineJob(ContainerCommandLineJob):
    def __init__(
        self,
        builder: Builder,
        joborder: CWLObjectType,
        make_path_mapper: Callable[[list[CWLObjectType], str, RuntimeContext, bool], PathMapper],
        requirements: list[CWLObjectType],
        hints: list[CWLObjectType],
        name: str,
    ) -> None:
        """Builder for invoking the Singularty software container engine."""
        super().__init__(builder, joborder, make_path_mapper, requirements, hints, name)

    @staticmethod
    def get_image(
        dockerRequirement: dict[str, str],
        pull_image: bool,
        tmp_outdir_prefix: str,
        force_pull: bool = False,
        sandbox_base_path: str | None = None,
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

        with _IMAGES_LOCK:
            if "dockerImageId" in dockerRequirement:
                d_image_id = dockerRequirement["dockerImageId"]
                if d_image_id in _IMAGES:
                    if (resolved_image_id := _IMAGES[d_image_id]) != d_image_id:
                        dockerRequirement["dockerImage_id"] = resolved_image_id
                    return True
                if d_image_id.startswith("/"):
                    _logger.info(
                        SourceLine(dockerRequirement, "dockerImageId").makeError(
                            f"Non-portable: using an absolute file path in a 'dockerImageId': {d_image_id}"
                        )
                    )

        docker_req = copy.deepcopy(dockerRequirement)  # thread safety
        if "CWL_SINGULARITY_CACHE" in os.environ:
            cache_folder = os.environ["CWL_SINGULARITY_CACHE"]
        elif is_version_2_6() and "SINGULARITY_PULLFOLDER" in os.environ:
            cache_folder = os.environ["SINGULARITY_PULLFOLDER"]

        if os.environ.get("CWL_SINGULARITY_IMAGES", None):
            image_base_path = os.environ["CWL_SINGULARITY_IMAGES"]
        else:
            image_base_path = cache_folder if cache_folder else ""

        if not sandbox_base_path:
            sandbox_base_path = os.path.abspath(image_base_path)
        else:
            sandbox_base_path = os.path.abspath(sandbox_base_path)

        if "dockerFile" in docker_req:
            if cache_folder is None:  # if environment variables were not set
                cache_folder = create_tmp_dir(tmp_outdir_prefix)

            absolute_path = os.path.abspath(cache_folder)
            if "dockerImageId" in docker_req:
                image_name = docker_req["dockerImageId"]
            else:
                image_name = hashlib.md5(  # nosec
                    json_dumps(dockerRequirement, separators=(",", ":"), sort_keys=True).encode(
                        "utf-8"
                    )
                ).hexdigest()
            if is_version_3_or_newer():
                image_name = _normalize_sif_id(image_name)
            else:
                image_name = _normalize_image_id(image_name)
            image_name = os.path.join(absolute_path, image_name)
            docker_req["dockerImageId"] = image_name
            if os.path.exists(image_name):
                found = True
            if found is False:
                dockerfile_path = os.path.join(absolute_path, "Dockerfile")
                singularityfile_path = dockerfile_path + ".def"
                with open(dockerfile_path, "w") as dfile:
                    dfile.write(docker_req["dockerFile"])

                docker_recipe = DockerParser(dockerfile_path).parse()
                docker_recipe["spython-base"].entrypoint = ""
                singularityfile = SingularityWriter(docker_recipe).convert()
                with open(singularityfile_path, "w") as file:
                    file.write(singularityfile)

                # if you do not set APPTAINER_TMPDIR will crash
                # WARNING: 'nodev' mount option set on /tmp, it could be a
                #          source of failure during build process
                # FATAL:   Unable to create build: 'noexec' mount option set on
                #          /tmp, temporary root filesystem won't be usable at this location
                os.environ["APPTAINER_TMPDIR"] = absolute_path
                singularity_options = ["--fakeroot"] if not shutil.which("proot") else []
                Client.build(
                    recipe=singularityfile_path,
                    build_folder=absolute_path,
                    image=image_name,
                    sudo=False,
                    options=singularity_options,
                )
                found = True
        elif "dockerImageId" not in docker_req and "dockerPull" in docker_req:
            # looking for local singularity sandbox image and handle it as a local image
            sandbox_image_path = os.path.join(sandbox_base_path, dockerRequirement["dockerPull"])
            if os.path.isdir(sandbox_image_path) and _inspect_singularity_sandbox_image(
                sandbox_image_path
            ):
                docker_req["dockerImageId"] = sandbox_image_path
                _logger.info(
                    "Using local Singularity sandbox image found in %s",
                    sandbox_image_path,
                )
                found = True
            else:
                match = re.search(pattern=r"([a-z]*://)", string=docker_req["dockerPull"])
                img_name = _normalize_image_id(docker_req["dockerPull"])
                candidates.append(img_name)
                if is_version_3_or_newer():
                    sif_name = _normalize_sif_id(docker_req["dockerPull"])
                    candidates.append(sif_name)
                    docker_req["dockerImageId"] = sif_name
                else:
                    docker_req["dockerImageId"] = img_name
                if not match:
                    docker_req["dockerPull"] = "docker://" + docker_req["dockerPull"]
        elif "dockerImageId" in docker_req:
            sandbox_image_path = os.path.join(sandbox_base_path, dockerRequirement["dockerImageId"])
            # handling local singularity sandbox image
            if os.path.isdir(sandbox_image_path) and _inspect_singularity_sandbox_image(
                sandbox_image_path
            ):
                _logger.info(
                    "Using local Singularity sandbox image found in %s",
                    sandbox_image_path,
                )
                docker_req["dockerImageId"] = sandbox_image_path
                found = True
            else:
                if os.path.isfile(docker_req["dockerImageId"]):
                    found = True
                candidates.append(docker_req["dockerImageId"])
                candidates.append(_normalize_image_id(docker_req["dockerImageId"]))
                if is_version_3_or_newer():
                    candidates.append(_normalize_sif_id(docker_req["dockerImageId"]))

        if not found and len(candidates) > 0:
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
                                    "Using local copy of Singularity image %s found in %s",
                                    entry,
                                    dirpath,
                                )
                                docker_req["dockerImageId"] = path
                                found = True
        if (force_pull or not found) and pull_image:
            cmd: list[str] = []
            if "dockerPull" in docker_req:
                if image_base_path:
                    env = os.environ.copy()
                    if is_version_2_6():
                        env["SINGULARITY_PULLFOLDER"] = image_base_path
                        cmd = [
                            "singularity",
                            "pull",
                            "--force",
                            "--name",
                            docker_req["dockerImageId"],
                            str(docker_req["dockerPull"]),
                        ]
                    else:
                        cmd = [
                            "singularity",
                            "pull",
                            "--force",
                            "--name",
                            "{}/{}".format(image_base_path, docker_req["dockerImageId"]),
                            str(docker_req["dockerPull"]),
                        ]

                    _logger.info(str(cmd))
                    check_call(cmd, env=env, stdout=sys.stderr)  # nosec
                    docker_req["dockerImageId"] = "{}/{}".format(
                        image_base_path, docker_req["dockerImageId"]
                    )
                    found = True
                else:
                    cmd = [
                        "singularity",
                        "pull",
                        "--force",
                        "--name",
                        str(docker_req["dockerImageId"]),
                        str(docker_req["dockerPull"]),
                    ]
                    _logger.info(str(cmd))
                    check_call(cmd, stdout=sys.stderr)  # nosec
                    found = True

            elif "dockerLoad" in docker_req:
                if is_version_3_1_or_newer():
                    if "dockerImageId" in docker_req:
                        name = "{}.sif".format(docker_req["dockerImageId"])
                    else:
                        name = "{}.sif".format(docker_req["dockerLoad"])
                    cmd = [
                        "singularity",
                        "build",
                        name,
                        "docker-archive://{}".format(docker_req["dockerLoad"]),
                    ]
                    _logger.info(str(cmd))
                    check_call(cmd, stdout=sys.stderr)  # nosec
                    found = True
                    docker_req["dockerImageId"] = name
                else:
                    raise SourceLine(docker_req, "dockerLoad", WorkflowException, debug).makeError(
                        "dockerLoad is not currently supported when using the "
                        "Singularity runtime (version less than 3.1) for Docker containers."
                    )
            elif "dockerImport" in docker_req:
                raise SourceLine(docker_req, "dockerImport", WorkflowException, debug).makeError(
                    "dockerImport is not currently supported when using the "
                    "Singularity runtime for Docker containers."
                )
        if found:
            with _IMAGES_LOCK:
                if "dockerImageId" in dockerRequirement:
                    _IMAGES[dockerRequirement["dockerImageId"]] = docker_req["dockerImageId"]
                dockerRequirement.clear()
                dockerRequirement |= docker_req
                if "dockerImageId" in docker_req:
                    _IMAGES[docker_req["dockerImageId"]] = docker_req["dockerImageId"]
        return found

    def get_from_requirements(
        self,
        r: CWLObjectType,
        pull_image: bool,
        force_pull: bool,
        tmp_outdir_prefix: str,
        image_base_path: str | None = None,
    ) -> str | None:
        """
        Return the filename of the Singularity image.

        (e.g. hello-world-latest.{img,sif}).
        """
        if not bool(shutil.which("singularity")):
            raise WorkflowException("singularity executable is not available")

        if not self.get_image(
            cast(dict[str, str], r),
            pull_image,
            tmp_outdir_prefix,
            force_pull,
            sandbox_base_path=image_base_path,
        ):
            raise WorkflowException(f"Container image not found for {r}")

        return os.path.abspath(cast(str, r["dockerImageId"]))

    @staticmethod
    def append_volume(runtime: list[str], source: str, target: str, writable: bool = False) -> None:
        """Add binding arguments to the runtime list."""
        if is_version_3_9_or_newer():
            DockerCommandLineJob.append_volume(runtime, source, target, writable, skip_mkdirs=True)
        else:
            runtime.append("--bind")
            # Mounts are writable by default, so 'rw' is optional and not
            # supported (due to a bug) in some 3.6 series releases.
            vol = f"{source}:{target}"
            if not writable:
                vol += ":ro"
            runtime.append(vol)

    def add_file_or_directory_volume(
        self, runtime: list[str], volume: MapperEnt, host_outdir_tgt: str | None
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
        runtime: list[str],
        volume: MapperEnt,
        host_outdir_tgt: str | None,
        tmpdir_prefix: str,
    ) -> None:
        if host_outdir_tgt is not None and not is_version_3_4_or_newer():
            # workaround for lack of overlapping mounts in Singularity <3.4
            if self.inplace_update:
                try:
                    os.link(os.path.realpath(volume.resolved), host_outdir_tgt)
                except OSError:
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
        runtime: list[str],
        volume: MapperEnt,
        host_outdir_tgt: str | None,
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
                    self.append_volume(runtime, volume.resolved, volume.target, writable=True)
                else:
                    if not host_outdir_tgt:
                        tmpdir = create_tmp_dir(tmpdir_prefix)
                        new_dir = os.path.join(tmpdir, os.path.basename(volume.resolved))
                        shutil.copytree(volume.resolved, new_dir)
                        self.append_volume(runtime, new_dir, volume.target, writable=True)
                    else:
                        shutil.copytree(volume.resolved, host_outdir_tgt)
                    ensure_writable(host_outdir_tgt or new_dir)

    def _required_env(self) -> dict[str, str]:
        return {
            "TMPDIR": self.CONTAINER_TMPDIR,
            "HOME": self.builder.outdir,
        }

    def create_runtime(
        self, env: MutableMapping[str, str], runtime_context: RuntimeContext
    ) -> tuple[list[str], str | None]:
        """Return the Singularity runtime list of commands and options."""
        any_path_okay = self.builder.get_requirement("DockerRequirement")[1] or False

        runtime = [
            "singularity",
            "--quiet",
            "run" if (is_apptainer_1_1_or_newer() or is_version_3_10_or_newer()) else "exec",
            "--contain",
            "--ipc",
            "--cleanenv",
        ]
        if is_apptainer_1_1_or_newer() or is_version_3_10_or_newer():
            runtime.append("--no-eval")

        if singularity_supports_userns():
            runtime.append("--userns")
        else:
            runtime.append("--pid")

        container_HOME: str | None = None
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
