"""Enables Docker software containers via the {dx-,u,}docker runtimes."""
from __future__ import absolute_import

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
from .pathmapper import PathMapper  # pylint: disable=unused-import
from .pathmapper import ensure_writable
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
    if not path:
        return
    if onWindows():
        path = path.lower()
    mounts = _get_docker_machine_mounts()
    if mounts:
        found = False
        for mount in mounts:
            if onWindows():
                mount = mount.lower()
            if path.startswith(mount):
                found = True
                break
        if not found:
            raise WorkflowException(
                "Input path {path} is not in the list of host paths mounted "
                "into the Docker virtual machine named {name}. Already mounted "
                "paths: {mounts}.\n"
                "See https://docs.docker.com/toolbox/toolbox_install_windows/"
                "#optional-add-shared-directories for instructions on how to "
                "add this path to your VM.".format(
                    path=path, name=os.environ["DOCKER_MACHINE_NAME"],
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
                              req,                    # type: bool
                              pull_image,             # type: bool
                              force_pull=False,       # type: bool
                              tmp_outdir_prefix=DEFAULT_TMP_PREFIX  # type: Text
                             ):  # type: (...) -> Optional[Text]
        if r:
            errmsg = None
            try:
                subprocess.check_output(["docker", "version"])
            except subprocess.CalledProcessError as err:
                errmsg = "Cannot communicate with docker daemon: " + Text(err)
            except OSError as err:
                errmsg = "'docker' executable not found: " + Text(err)

            if errmsg:
                if req:
                    raise WorkflowException(errmsg)
                else:
                    return None

            if self.get_image(r, pull_image, force_pull, tmp_outdir_prefix):
                return r["dockerImageId"]
            if req:
                raise WorkflowException(u"Docker image %s not found" % r["dockerImageId"])

        return None

    def add_volumes(self, pathmapper, runtime, secret_store=None):
        # type: (PathMapper, List[Text], SecretStore) -> None
        """Append volume mappings to the runtime option list."""

        host_outdir = self.outdir
        container_outdir = self.builder.outdir
        for _, vol in pathmapper.items():
            if not vol.staged:
                continue
            host_outdir_tgt = None  # type: Optional[Text]
            if vol.target.startswith(container_outdir+"/"):
                host_outdir_tgt = os.path.join(
                    host_outdir, vol.target[len(container_outdir)+1:])
            if vol.type in ("File", "Directory"):
                if not vol.resolved.startswith("_:"):
                    _check_docker_machine_path(docker_windows_path_adjust(
                        vol.resolved))
                    runtime.append(u"--volume=%s:%s:ro" % (
                        docker_windows_path_adjust(vol.resolved),
                        docker_windows_path_adjust(vol.target)))
            elif vol.type == "WritableFile":
                if self.inplace_update:
                    runtime.append(u"--volume=%s:%s:rw" % (
                        docker_windows_path_adjust(vol.resolved),
                        docker_windows_path_adjust(vol.target)))
                else:
                    if host_outdir_tgt:
                        shutil.copy(vol.resolved, host_outdir_tgt)
                        ensure_writable(host_outdir_tgt)
                    else:
                        raise WorkflowException(
                            "Unable to compute host_outdir_tgt for "
                            "WriteableFile.")
            elif vol.type == "WritableDirectory":
                if vol.resolved.startswith("_:"):
                    if host_outdir_tgt:
                        os.makedirs(host_outdir_tgt, 0o0755)
                    else:
                        raise WorkflowException(
                            "Unable to compute host_outdir_tgt for "
                            "WritableDirectory.")
                else:
                    if self.inplace_update:
                        runtime.append(u"--volume=%s:%s:rw" % (
                            docker_windows_path_adjust(vol.resolved),
                            docker_windows_path_adjust(vol.target)))
                    else:
                        if host_outdir_tgt:
                            shutil.copytree(vol.resolved, host_outdir_tgt)
                            ensure_writable(host_outdir_tgt)
                        else:
                            raise WorkflowException(
                                "Unable to compute host_outdir_tgt for "
                                "WritableDirectory.")
            elif vol.type == "CreateFile":
                if secret_store:
                    contents = secret_store.retrieve(vol.resolved)
                else:
                    contents = vol.resolved
                if host_outdir_tgt:
                    with open(host_outdir_tgt, "wb") as file_literal:
                        file_literal.write(contents.encode("utf-8"))
                else:
                    tmp_fd, createtmp = tempfile.mkstemp(dir=self.tmpdir)
                    with os.fdopen(tmp_fd, "wb") as file_literal:
                        file_literal.write(contents.encode("utf-8"))
                    runtime.append(u"--volume=%s:%s:rw" % (
                        docker_windows_path_adjust(os.path.realpath(createtmp)),
                        vol.target))

    def create_runtime(self, env, runtimeContext):
        # type: (MutableMapping[Text, Text], RuntimeContext) -> List
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

        self.add_volumes(self.pathmapper, runtime, secret_store=runtimeContext.secret_store)
        if self.generatemapper:
            self.add_volumes(self.generatemapper, runtime, secret_store=runtimeContext.secret_store)

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

            if self.stdout:
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
        if runtimeContext.record_container_id:
            cidfile_dir = runtimeContext.cidfile_dir
            if cidfile_dir != "":
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
            if runtimeContext.cidfile_prefix != "":
                cidfile_name = str(runtimeContext.cidfile_prefix + "-" + cidfile_name)
            cidfile_path = os.path.join(cidfile_dir, cidfile_name)
            runtime.append(u"--cidfile=%s" % cidfile_path)

        for key, value in self.environment.items():
            runtime.append(u"--env=%s=%s" % (key, value))

        if runtimeContext.strict_memory_limit and not user_space_docker_cmd:
            runtime.append("--memory=%dm" % self.builder.resources["ram"])
        elif not user_space_docker_cmd:
            res_req = self.builder.get_requirement("ResourceRequirement")[0]
            if res_req and ("ramMin" in res_req or "ramMax" is res_req):
                _logger.warning(
                    u"[job %s] Skipping Docker software container '--memory' limit "
                    "despite presence of ResourceRequirement with ramMin "
                    "and/or ramMax setting. Consider running with "
                    "--strict-memory-limit for increased portability "
                    "assurance.", self.name)

        return runtime
