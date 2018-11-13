"""Enables Docker software containers via the {dx-,u,}docker runtimes."""
from __future__ import absolute_import

from distutils import spawn
import datetime
import os
import re
import shutil
import sys
import tempfile
import threading
from io import open  # pylint: disable=redefined-builtin
from typing import Dict, List, MutableMapping, Optional, Set

import requests
from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .context import RuntimeContext  # pylint: disable=unused-import
from .docker_id import docker_vm_id
from .errors import WorkflowException
from .job import ContainerCommandLineJob
from .loghandler import _logger
from .pathmapper import PathMapper, MapperEnt  # pylint: disable=unused-import
from .pathmapper import ensure_writable, ensure_non_writable
from .secrets import SecretStore  # pylint: disable=unused-import
from .utils import (DEFAULT_TMP_PREFIX, docker_windows_path_adjust, onWindows,
                    subprocess)


_IMAGES = set()  # type: Set[Text]
_IMAGES_LOCK = threading.Lock()
__docker_machine_mounts = None  # type: Optional[List[Text]]
__docker_machine_mounts_lock = threading.Lock()

def _get_docker_machine_mounts():  # type: () -> List[Text]
    global __docker_machine_mounts
    if __docker_machine_mounts is None:
        with __docker_machine_mounts_lock:
            if 'DOCKER_MACHINE_NAME' not in os.environ:
                __docker_machine_mounts = []
            else:
                __docker_machine_mounts = [
                    u'/' + line.split(None, 1)[0] for line in
                    subprocess.check_output(
                        ['docker-machine', 'ssh',
                         os.environ['DOCKER_MACHINE_NAME'], 'mount', '-t',
                         'vboxsf'],
                        universal_newlines=True).splitlines()]
    return __docker_machine_mounts

def _check_docker_machine_path(path):  # type: (Optional[Text]) -> None
    if path is None:
        return
    if onWindows():
        path = path.lower()
    mounts = _get_docker_machine_mounts()

    found = False
    for mount in mounts:
        if onWindows():
            mount = mount.lower()
        if path.startswith(mount):
            found = True
            break

    if not found and mounts:
        name = os.environ.get("DOCKER_MACHINE_NAME", '???')
        raise WorkflowException(
            "Input path {path} is not in the list of host paths mounted "
            "into the Docker virtual machine named {name}. Already mounted "
            "paths: {mounts}.\n"
            "See https://docs.docker.com/toolbox/toolbox_install_windows/"
            "#optional-add-shared-directories for instructions on how to "
            "add this path to your VM.".format(
                path=path, name=name,
                mounts=mounts))

class DockerCommandLineJob(ContainerCommandLineJob):
    """Runs a CommandLineJob in a sofware container using the Docker engine."""

    @staticmethod
    def get_image(docker_requirement,     # type: Dict[Text, Text]
                  pull_image,             # type: bool
                  force_pull=False,       # type: bool
                  tmp_outdir_prefix=DEFAULT_TMP_PREFIX  # type: Text
                 ):  # type: (...) -> bool
        """
        Retrieve the relevant Docker container image.

        Returns True upon success
        """
        found = False

        if "dockerImageId" not in docker_requirement \
                and "dockerPull" in docker_requirement:
            docker_requirement["dockerImageId"] = docker_requirement["dockerPull"]

        with _IMAGES_LOCK:
            if docker_requirement["dockerImageId"] in _IMAGES:
                return True

        for line in subprocess.check_output(
                ["docker", "images", "--no-trunc", "--all"]).decode('utf-8').splitlines():
            try:
                match = re.match(r"^([^ ]+)\s+([^ ]+)\s+([^ ]+)", line)
                split = docker_requirement["dockerImageId"].split(":")
                if len(split) == 1:
                    split.append("latest")
                elif len(split) == 2:
                    #  if split[1] doesn't  match valid tag names, it is a part of repository
                    if not re.match(r'[\w][\w.-]{0,127}', split[1]):
                        split[0] = split[0] + ":" + split[1]
                        split[1] = "latest"
                elif len(split) == 3:
                    if re.match(r'[\w][\w.-]{0,127}', split[2]):
                        split[0] = split[0] + ":" + split[1]
                        split[1] = split[2]
                        del split[2]

                # check for repository:tag match or image id match
                if (match and
                        ((split[0] == match.group(1) and split[1] == match.group(2)) or
                         docker_requirement["dockerImageId"] == match.group(3))):
                    found = True
                    break
            except ValueError:
                pass

        if (force_pull or not found) and pull_image:
            cmd = []  # type: List[Text]
            if "dockerPull" in docker_requirement:
                cmd = ["docker", "pull", str(docker_requirement["dockerPull"])]
                _logger.info(Text(cmd))
                subprocess.check_call(cmd, stdout=sys.stderr)
                found = True
            elif "dockerFile" in docker_requirement:
                dockerfile_dir = str(tempfile.mkdtemp(prefix=tmp_outdir_prefix))
                with open(os.path.join(
                        dockerfile_dir, "Dockerfile"), "wb") as dfile:
                    dfile.write(docker_requirement["dockerFile"].encode('utf-8'))
                cmd = ["docker", "build", "--tag=%s" %
                       str(docker_requirement["dockerImageId"]), dockerfile_dir]
                _logger.info(Text(cmd))
                subprocess.check_call(cmd, stdout=sys.stderr)
                found = True
            elif "dockerLoad" in docker_requirement:
                cmd = ["docker", "load"]
                _logger.info(Text(cmd))
                if os.path.exists(docker_requirement["dockerLoad"]):
                    _logger.info(u"Loading docker image from %s", docker_requirement["dockerLoad"])
                    with open(docker_requirement["dockerLoad"], "rb") as dload:
                        loadproc = subprocess.Popen(cmd, stdin=dload, stdout=sys.stderr)
                else:
                    loadproc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                                stdout=sys.stderr)
                    assert loadproc.stdin is not None
                    _logger.info(u"Sending GET request to %s", docker_requirement["dockerLoad"])
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
                        "Docker load returned non-zero exit status %i" % (rcode))
                found = True
            elif "dockerImport" in docker_requirement:
                cmd = ["docker", "import", str(docker_requirement["dockerImport"]),
                       str(docker_requirement["dockerImageId"])]
                _logger.info(Text(cmd))
                subprocess.check_call(cmd, stdout=sys.stderr)
                found = True

        if found:
            with _IMAGES_LOCK:
                _IMAGES.add(docker_requirement["dockerImageId"])

        return found

    def get_from_requirements(self,
                              r,                      # type: Dict[Text, Text]
                              pull_image,             # type: bool
                              force_pull=False,       # type: bool
                              tmp_outdir_prefix=DEFAULT_TMP_PREFIX  # type: Text
                             ):  # type: (...) -> Optional[Text]
        if not spawn.find_executable('docker'):
            raise WorkflowException("docker executable is not available")


        if self.get_image(r, pull_image, force_pull, tmp_outdir_prefix):
            return r["dockerImageId"]
        raise WorkflowException(u"Docker image %s not found" % r["dockerImageId"])

    @staticmethod
    def append_volume(runtime, source, target, writable=False):
        # type: (List[Text], Text, Text, bool) -> None
        """Add binding arguments to the runtime list."""
        runtime.append(u"--volume={}:{}:{}".format(
            docker_windows_path_adjust(source),
            docker_windows_path_adjust(target), "rw" if writable else "ro"))

    def add_file_or_directory_volume(self,
                                     runtime,         # type: List[Text]
                                     volume,          # type: MapperEnt
                                     host_outdir_tgt  # type: Optional[Text]
                                     ):  # type: (...) -> None
        """Append volume a file/dir mapping to the runtime option list."""
        if not volume.resolved.startswith("_:"):
            _check_docker_machine_path(docker_windows_path_adjust(
                volume.resolved))
            self.append_volume(runtime, volume.resolved, volume.target)

    def add_writable_file_volume(self,
                                 runtime,         # type: List[Text]
                                 volume,          # type: MapperEnt
                                 host_outdir_tgt  # type: Optional[Text]
                                ):  # type: (...) -> None
        """Append a writable file mapping to the runtime option list."""
        if self.inplace_update:
            self.append_volume(runtime, volume.resolved, volume.target,
                               writable=True)
        else:
            if host_outdir_tgt:
                # shortcut, just copy to the output directory
                # which is already going to be mounted
                shutil.copy(volume.resolved, host_outdir_tgt)
            else:
                tmpdir = tempfile.mkdtemp(dir=self.tmpdir)
                file_copy = os.path.join(
                    tmpdir, os.path.basename(volume.resolved))
                shutil.copy(volume.resolved, file_copy)
                self.append_volume(runtime, file_copy, volume.target,
                                   writable=True)
            ensure_writable(host_outdir_tgt or file_copy)

    def add_writable_directory_volume(self,
                                      runtime,         # type: List[Text]
                                      volume,          # type: MapperEnt
                                      host_outdir_tgt  # type: Optional[Text]
                                     ):  # type: (...) -> None
        """Append a writable directory mapping to the runtime option list."""
        if volume.resolved.startswith("_:"):
            # Synthetic directory that needs creating first
            if not host_outdir_tgt:
                new_dir = os.path.join(
                    tempfile.mkdtemp(dir=self.tmpdir),
                    os.path.basename(volume.target))
                self.append_volume(runtime, new_dir, volume.target,
                                   writable=True)
            elif not os.path.exists(host_outdir_tgt):
                os.makedirs(host_outdir_tgt, 0o0755)
        else:
            if self.inplace_update:
                self.append_volume(runtime, volume.resolved, volume.target,
                                   writable=True)
            else:
                if not host_outdir_tgt:
                    tmpdir = tempfile.mkdtemp(dir=self.tmpdir)
                    new_dir = os.path.join(
                        tmpdir, os.path.basename(volume.resolved))
                    shutil.copytree(volume.resolved, new_dir)
                    self.append_volume(
                        runtime, new_dir, volume.target,
                        writable=True)
                else:
                    shutil.copytree(volume.resolved, host_outdir_tgt)
                ensure_writable(host_outdir_tgt or new_dir)

    def create_runtime(self, env, runtimeContext):
        # type: (MutableMapping[Text, Text], RuntimeContext) -> List
        any_path_okay = self.builder.get_requirement("DockerRequirement")[1] \
            or False
        user_space_docker_cmd = runtimeContext.user_space_docker_cmd
        if user_space_docker_cmd:
            if 'udocker' in user_space_docker_cmd and not runtimeContext.debug:
                runtime = [user_space_docker_cmd, u"--quiet", u"run"]
                # udocker 1.1.1 will output diagnostic messages to stdout
                # without this
            else:
                runtime = [user_space_docker_cmd, u"run"]
        else:
            runtime = [u"docker", u"run", u"-i"]

        runtime.append(u"--volume=%s:%s:rw" % (
            docker_windows_path_adjust(os.path.realpath(self.outdir)),
            self.builder.outdir))
        runtime.append(u"--volume=%s:%s:rw" % (
            docker_windows_path_adjust(os.path.realpath(self.tmpdir)), "/tmp"))

        self.add_volumes(self.pathmapper, runtime, any_path_okay=True,
                         secret_store=runtimeContext.secret_store)
        if self.generatemapper is not None:
            self.add_volumes(
                self.generatemapper, runtime, any_path_okay=any_path_okay,
                secret_store=runtimeContext.secret_store)

        if user_space_docker_cmd:
            runtime = [x.replace(":ro", "") for x in runtime]
            runtime = [x.replace(":rw", "") for x in runtime]

        runtime.append(u"--workdir=%s" % (
            docker_windows_path_adjust(self.builder.outdir)))
        if not user_space_docker_cmd:

            if not runtimeContext.no_read_only:
                runtime.append(u"--read-only=true")

            if self.networkaccess:
                if runtimeContext.custom_net:
                    runtime.append(u"--net={0}".format(runtimeContext.custom_net))
            else:
                runtime.append(u"--net=none")

            if self.stdout is not None:
                runtime.append("--log-driver=none")

            euid, egid = docker_vm_id()
            if not onWindows():
                # MS Windows does not have getuid() or geteuid() functions
                euid, egid = euid or os.geteuid(), egid or os.getgid()

            if runtimeContext.no_match_user is False \
                    and (euid is not None and egid is not None):
                runtime.append(u"--user=%d:%d" % (euid, egid))

        if runtimeContext.rm_container:
            runtime.append(u"--rm")

        runtime.append(u"--env=TMPDIR=/tmp")

        # spec currently says "HOME must be set to the designated output
        # directory." but spec might change to designated temp directory.
        # runtime.append("--env=HOME=/tmp")
        runtime.append(u"--env=HOME=%s" % self.builder.outdir)

        # add parameters to docker to write a container ID file
        if runtimeContext.record_container_id is True:
            cidfile_dir = runtimeContext.cidfile_dir
            if cidfile_dir is not None:
                if not os.path.isdir(cidfile_dir):
                    _logger.error("--cidfile-dir %s error:\n%s", cidfile_dir,
                                  cidfile_dir + " is not a directory or "
                                  "directory doesn't exist, please check it first")
                    exit(2)
                if not os.path.exists(cidfile_dir):
                    _logger.error("--cidfile-dir %s error:\n%s", cidfile_dir,
                                  "directory doesn't exist, please create it first")
                    exit(2)
            else:
                cidfile_dir = os.getcwd()
            cidfile_name = datetime.datetime.now().strftime("%Y%m%d%H%M%S-%f") + ".cid"
            if runtimeContext.cidfile_prefix is not None:
                cidfile_name = str(runtimeContext.cidfile_prefix + "-" + cidfile_name)
            cidfile_path = os.path.join(cidfile_dir, cidfile_name)
            runtime.append(u"--cidfile=%s" % cidfile_path)

        for key, value in self.environment.items():
            runtime.append(u"--env=%s=%s" % (key, value))

        if runtimeContext.strict_memory_limit and not user_space_docker_cmd:
            runtime.append("--memory=%dm" % self.builder.resources["ram"])
        elif not user_space_docker_cmd:
            res_req, _ = self.builder.get_requirement("ResourceRequirement")
            if res_req is not None and ("ramMin" in res_req or "ramMax" is res_req):
                _logger.warning(
                    u"[job %s] Skipping Docker software container '--memory' limit "
                    "despite presence of ResourceRequirement with ramMin "
                    "and/or ramMax setting. Consider running with "
                    "--strict-memory-limit for increased portability "
                    "assurance.", self.name)

        return runtime
