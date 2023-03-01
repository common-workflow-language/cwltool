"""Enables Docker software containers via the {u,}docker or podman runtimes."""

import csv
import datetime
import math
import os
import re
import shutil
import subprocess  # nosec
import sys
import threading
from io import StringIO  # pylint: disable=redefined-builtin
from typing import Callable, Dict, List, MutableMapping, Optional, Set, Tuple, cast

import requests

from .builder import Builder
from .context import RuntimeContext
from .docker_id import docker_vm_id
from .errors import WorkflowException
from .job import ContainerCommandLineJob
from .loghandler import _logger
from .pathmapper import MapperEnt, PathMapper
from .utils import CWLObjectType, create_tmp_dir, ensure_writable

_IMAGES: Set[str] = set()
_IMAGES_LOCK = threading.Lock()
__docker_machine_mounts: Optional[List[str]] = None
__docker_machine_mounts_lock = threading.Lock()


def _get_docker_machine_mounts() -> List[str]:
    global __docker_machine_mounts
    if __docker_machine_mounts is None:
        with __docker_machine_mounts_lock:
            if "DOCKER_MACHINE_NAME" not in os.environ:
                __docker_machine_mounts = []
            else:
                __docker_machine_mounts = [
                    "/" + line.split(None, 1)[0]
                    for line in subprocess.check_output(  # nosec
                        [
                            "docker-machine",
                            "ssh",
                            os.environ["DOCKER_MACHINE_NAME"],
                            "mount",
                            "-t",
                            "vboxsf",
                        ],
                        universal_newlines=True,
                    ).splitlines()
                ]
    return __docker_machine_mounts


def _check_docker_machine_path(path: Optional[str]) -> None:
    if path is None:
        return
    mounts = _get_docker_machine_mounts()

    found = False
    for mount in mounts:
        if path.startswith(mount):
            found = True
            break

    if not found and mounts:
        name = os.environ.get("DOCKER_MACHINE_NAME", "???")
        raise WorkflowException(
            "Input path {path} is not in the list of host paths mounted "
            "into the Docker virtual machine named {name}. Already mounted "
            "paths: {mounts}.\n"
            "See https://docs.docker.com/toolbox/toolbox_install_windows/"
            "#optional-add-shared-directories for instructions on how to "
            "add this path to your VM.".format(path=path, name=name, mounts=mounts)
        )


class DockerCommandLineJob(ContainerCommandLineJob):
    """Runs a :py:class:`~cwltool.job.CommandLineJob` in a software container using the Docker engine."""

    def __init__(
        self,
        builder: Builder,
        joborder: CWLObjectType,
        make_path_mapper: Callable[[List[CWLObjectType], str, RuntimeContext, bool], PathMapper],
        requirements: List[CWLObjectType],
        hints: List[CWLObjectType],
        name: str,
    ) -> None:
        """Initialize a command line builder using the Docker software container engine."""
        super().__init__(builder, joborder, make_path_mapper, requirements, hints, name)
        self.docker_exec = "docker"

    def get_image(
        self,
        docker_requirement: Dict[str, str],
        pull_image: bool,
        force_pull: bool,
        tmp_outdir_prefix: str,
    ) -> bool:
        """
        Retrieve the relevant Docker container image.

        :returns: True upon success
        """
        found = False

        if "dockerImageId" not in docker_requirement and "dockerPull" in docker_requirement:
            docker_requirement["dockerImageId"] = docker_requirement["dockerPull"]

        with _IMAGES_LOCK:
            if docker_requirement["dockerImageId"] in _IMAGES:
                return True

        for line in (
            subprocess.check_output([self.docker_exec, "images", "--no-trunc", "--all"])  # nosec
            .decode("utf-8")
            .splitlines()
        ):
            try:
                match = re.match(r"^([^ ]+)\s+([^ ]+)\s+([^ ]+)", line)
                split = docker_requirement["dockerImageId"].split(":")
                if len(split) == 1:
                    split.append("latest")
                elif len(split) == 2:
                    #  if split[1] doesn't  match valid tag names, it is a part of repository
                    if not re.match(r"[\w][\w.-]{0,127}", split[1]):
                        split[0] = split[0] + ":" + split[1]
                        split[1] = "latest"
                elif len(split) == 3:
                    if re.match(r"[\w][\w.-]{0,127}", split[2]):
                        split[0] = split[0] + ":" + split[1]
                        split[1] = split[2]
                        del split[2]

                # check for repository:tag match or image id match
                if match and (
                    (split[0] == match.group(1) and split[1] == match.group(2))
                    or docker_requirement["dockerImageId"] == match.group(3)
                ):
                    found = True
                    break
            except ValueError:
                pass

        if (force_pull or not found) and pull_image:
            cmd: List[str] = []
            if "dockerPull" in docker_requirement:
                cmd = [self.docker_exec, "pull", str(docker_requirement["dockerPull"])]
                _logger.info(str(cmd))
                subprocess.check_call(cmd, stdout=sys.stderr)  # nosec
                found = True
            elif "dockerFile" in docker_requirement:
                dockerfile_dir = create_tmp_dir(tmp_outdir_prefix)
                with open(os.path.join(dockerfile_dir, "Dockerfile"), "w") as dfile:
                    dfile.write(docker_requirement["dockerFile"])
                cmd = [
                    self.docker_exec,
                    "build",
                    "--tag=%s" % str(docker_requirement["dockerImageId"]),
                    dockerfile_dir,
                ]
                _logger.info(str(cmd))
                subprocess.check_call(cmd, stdout=sys.stderr)  # nosec
                found = True
            elif "dockerLoad" in docker_requirement:
                cmd = [self.docker_exec, "load"]
                _logger.info(str(cmd))
                if os.path.exists(docker_requirement["dockerLoad"]):
                    _logger.info(
                        "Loading docker image from %s",
                        docker_requirement["dockerLoad"],
                    )
                    with open(docker_requirement["dockerLoad"], "rb") as dload:
                        loadproc = subprocess.Popen(cmd, stdin=dload, stdout=sys.stderr)  # nosec
                else:
                    loadproc = subprocess.Popen(  # nosec
                        cmd, stdin=subprocess.PIPE, stdout=sys.stderr
                    )
                    assert loadproc.stdin is not None  # nosec
                    _logger.info("Sending GET request to %s", docker_requirement["dockerLoad"])
                    req = requests.get(docker_requirement["dockerLoad"], stream=True)
                    size = 0
                    for chunk in req.iter_content(1024 * 1024):
                        size += len(chunk)
                        _logger.info("\r%i bytes", size)
                        loadproc.stdin.write(chunk)
                    loadproc.stdin.close()
                rcode = loadproc.wait()
                if rcode != 0:
                    raise WorkflowException(
                        "Docker load returned non-zero exit status %i" % (rcode)
                    )
                found = True
            elif "dockerImport" in docker_requirement:
                cmd = [
                    self.docker_exec,
                    "import",
                    str(docker_requirement["dockerImport"]),
                    str(docker_requirement["dockerImageId"]),
                ]
                _logger.info(str(cmd))
                subprocess.check_call(cmd, stdout=sys.stderr)  # nosec
                found = True

        if found:
            with _IMAGES_LOCK:
                _IMAGES.add(docker_requirement["dockerImageId"])

        return found

    def get_from_requirements(
        self,
        r: CWLObjectType,
        pull_image: bool,
        force_pull: bool,
        tmp_outdir_prefix: str,
    ) -> Optional[str]:
        if not shutil.which(self.docker_exec):
            raise WorkflowException(f"{self.docker_exec} executable is not available")

        if self.get_image(cast(Dict[str, str], r), pull_image, force_pull, tmp_outdir_prefix):
            return cast(Optional[str], r["dockerImageId"])
        raise WorkflowException("Docker image %s not found" % r["dockerImageId"])

    @staticmethod
    def append_volume(runtime: List[str], source: str, target: str, writable: bool = False) -> None:
        """Add binding arguments to the runtime list."""
        options = [
            "type=bind",
            "source=" + source,
            "target=" + target,
        ]
        if not writable:
            options.append("readonly")
        output = StringIO()
        csv.writer(output).writerow(options)
        mount_arg = output.getvalue().strip()
        runtime.append(f"--mount={mount_arg}")
        # Unlike "--volume", "--mount" will fail if the volume doesn't already exist.
        if not os.path.exists(source):
            os.makedirs(source)

    def add_file_or_directory_volume(
        self, runtime: List[str], volume: MapperEnt, host_outdir_tgt: Optional[str]
    ) -> None:
        """Append volume a file/dir mapping to the runtime option list."""
        if not volume.resolved.startswith("_:"):
            _check_docker_machine_path(volume.resolved)
            self.append_volume(runtime, volume.resolved, volume.target)

    def add_writable_file_volume(
        self,
        runtime: List[str],
        volume: MapperEnt,
        host_outdir_tgt: Optional[str],
        tmpdir_prefix: str,
    ) -> None:
        """Append a writable file mapping to the runtime option list."""
        if self.inplace_update:
            self.append_volume(runtime, volume.resolved, volume.target, writable=True)
        else:
            if host_outdir_tgt:
                # shortcut, just copy to the output directory
                # which is already going to be mounted
                if not os.path.exists(os.path.dirname(host_outdir_tgt)):
                    os.makedirs(os.path.dirname(host_outdir_tgt))
                shutil.copy(volume.resolved, host_outdir_tgt)
            else:
                tmpdir = create_tmp_dir(tmpdir_prefix)
                file_copy = os.path.join(tmpdir, os.path.basename(volume.resolved))
                shutil.copy(volume.resolved, file_copy)
                self.append_volume(runtime, file_copy, volume.target, writable=True)
            ensure_writable(host_outdir_tgt or file_copy)

    def add_writable_directory_volume(
        self,
        runtime: List[str],
        volume: MapperEnt,
        host_outdir_tgt: Optional[str],
        tmpdir_prefix: str,
    ) -> None:
        """Append a writable directory mapping to the runtime option list."""
        if volume.resolved.startswith("_:"):
            # Synthetic directory that needs creating first
            if not host_outdir_tgt:
                new_dir = os.path.join(
                    create_tmp_dir(tmpdir_prefix),
                    os.path.basename(volume.target),
                )
                self.append_volume(runtime, new_dir, volume.target, writable=True)
            elif not os.path.exists(host_outdir_tgt):
                os.makedirs(host_outdir_tgt)
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

    def _required_env(self) -> Dict[str, str]:
        # spec currently says "HOME must be set to the designated output
        # directory." but spec might change to designated temp directory.
        # runtime.append("--env=HOME=/tmp")
        return {
            "TMPDIR": self.CONTAINER_TMPDIR,
            "HOME": self.builder.outdir,
        }

    def create_runtime(
        self, env: MutableMapping[str, str], runtimeContext: RuntimeContext
    ) -> Tuple[List[str], Optional[str]]:
        any_path_okay = self.builder.get_requirement("DockerRequirement")[1] or False
        user_space_docker_cmd = runtimeContext.user_space_docker_cmd
        if user_space_docker_cmd:
            if "udocker" in user_space_docker_cmd:
                if runtimeContext.debug:
                    runtime = [user_space_docker_cmd, "run", "--nobanner"]
                else:
                    runtime = [user_space_docker_cmd, "--quiet", "run", "--nobanner"]
            else:
                runtime = [user_space_docker_cmd, "run"]
        else:
            runtime = [self.docker_exec, "run", "-i"]
        if runtimeContext.podman:
            runtime.append("--userns=keep-id")
        self.append_volume(
            runtime, os.path.realpath(self.outdir), self.builder.outdir, writable=True
        )
        self.append_volume(
            runtime, os.path.realpath(self.tmpdir), self.CONTAINER_TMPDIR, writable=True
        )
        self.add_volumes(
            self.pathmapper,
            runtime,
            any_path_okay=True,
            secret_store=runtimeContext.secret_store,
            tmpdir_prefix=runtimeContext.tmpdir_prefix,
        )
        if self.generatemapper is not None:
            self.add_volumes(
                self.generatemapper,
                runtime,
                any_path_okay=any_path_okay,
                secret_store=runtimeContext.secret_store,
                tmpdir_prefix=runtimeContext.tmpdir_prefix,
            )

        if user_space_docker_cmd:
            runtime = [x.replace(":ro", "") for x in runtime]
            runtime = [x.replace(":rw", "") for x in runtime]

        runtime.append("--workdir=%s" % (self.builder.outdir))
        if not user_space_docker_cmd:
            if not runtimeContext.no_read_only:
                runtime.append("--read-only=true")

            if self.networkaccess:
                if runtimeContext.custom_net:
                    runtime.append(f"--net={runtimeContext.custom_net}")
            else:
                runtime.append("--net=none")

            if self.stdout is not None:
                runtime.append("--log-driver=none")

            euid, egid = docker_vm_id()
            euid, egid = euid or os.geteuid(), egid or os.getgid()

            if runtimeContext.no_match_user is False and (euid is not None and egid is not None):
                runtime.append("--user=%d:%d" % (euid, egid))

        if runtimeContext.rm_container:
            runtime.append("--rm")

        if self.builder.resources.get("cudaDeviceCount"):
            runtime.append("--gpus=" + str(self.builder.resources["cudaDeviceCount"]))

        cidfile_path: Optional[str] = None
        # add parameters to docker to write a container ID file
        if runtimeContext.user_space_docker_cmd is None:
            if runtimeContext.cidfile_dir:
                cidfile_dir = runtimeContext.cidfile_dir
                if not os.path.exists(str(cidfile_dir)):
                    _logger.error(
                        "--cidfile-dir %s error:\n%s",
                        cidfile_dir,
                        "directory doesn't exist, please create it first",
                    )
                    exit(2)
                if not os.path.isdir(cidfile_dir):
                    _logger.error(
                        "--cidfile-dir %s error:\n%s",
                        cidfile_dir,
                        cidfile_dir + " is not a directory, please check it first",
                    )
                    exit(2)
            else:
                cidfile_dir = runtimeContext.create_tmpdir()

            cidfile_name = datetime.datetime.now().strftime("%Y%m%d%H%M%S-%f") + ".cid"
            if runtimeContext.cidfile_prefix is not None:
                cidfile_name = str(runtimeContext.cidfile_prefix + "-" + cidfile_name)
            cidfile_path = os.path.join(cidfile_dir, cidfile_name)
            runtime.append("--cidfile=%s" % cidfile_path)
        for key, value in self.environment.items():
            runtime.append(f"--env={key}={value}")

        res_req, _ = self.builder.get_requirement("ResourceRequirement")

        if runtimeContext.strict_memory_limit and not user_space_docker_cmd:
            ram = self.builder.resources["ram"]
            runtime.append("--memory=%dm" % ram)
        elif not user_space_docker_cmd:
            if res_req and ("ramMin" in res_req or "ramMax" in res_req):
                _logger.warning(
                    "[job %s] Skipping Docker software container '--memory' limit "
                    "despite presence of ResourceRequirement with ramMin "
                    "and/or ramMax setting. Consider running with "
                    "--strict-memory-limit for increased portability "
                    "assurance.",
                    self.name,
                )
        if runtimeContext.strict_cpu_limit and not user_space_docker_cmd:
            cpus = math.ceil(self.builder.resources["cores"])
            runtime.append(f"--cpus={cpus}")
        elif not user_space_docker_cmd:
            if res_req and ("coresMin" in res_req or "coresMax" in res_req):
                _logger.warning(
                    "[job %s] Skipping Docker software container '--cpus' limit "
                    "despite presence of ResourceRequirement with coresMin "
                    "and/or coresMax setting. Consider running with "
                    "--strict-cpu-limit for increased portability "
                    "assurance.",
                    self.name,
                )

        return runtime, cidfile_path


class PodmanCommandLineJob(DockerCommandLineJob):
    """Runs a :py:class:`~cwltool.job.CommandLineJob` in a software container using the podman engine."""

    def __init__(
        self,
        builder: Builder,
        joborder: CWLObjectType,
        make_path_mapper: Callable[[List[CWLObjectType], str, RuntimeContext, bool], PathMapper],
        requirements: List[CWLObjectType],
        hints: List[CWLObjectType],
        name: str,
    ) -> None:
        """Initialize a command line builder using the Podman software container engine."""
        super().__init__(builder, joborder, make_path_mapper, requirements, hints, name)
        self.docker_exec = "podman"
