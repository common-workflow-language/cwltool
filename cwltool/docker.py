from __future__ import absolute_import

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from io import open

import datetime
import requests
from typing import (Dict, List, Text, Any, MutableMapping)

from .docker_id import docker_vm_id
from .errors import WorkflowException
from .job import ContainerCommandLineJob
from .pathmapper import PathMapper, ensure_writable
from .utils import docker_windows_path_adjust, onWindows

_logger = logging.getLogger("cwltool")


class DockerCommandLineJob(ContainerCommandLineJob):

    @staticmethod
    def get_image(dockerRequirement, pull_image, dry_run=False):
        # type: (Dict[Text, Text], bool, bool) -> bool
        found = False

        if "dockerImageId" not in dockerRequirement and "dockerPull" in dockerRequirement:
            dockerRequirement["dockerImageId"] = dockerRequirement["dockerPull"]

        for ln in subprocess.check_output(
                ["docker", "images", "--no-trunc", "--all"]).decode('utf-8').splitlines():
            try:
                m = re.match(r"^([^ ]+)\s+([^ ]+)\s+([^ ]+)", ln)
                sp = dockerRequirement["dockerImageId"].split(":")
                if len(sp) == 1:
                    sp.append("latest")
                elif len(sp) == 2:
                    #  if sp[1] doesn't  match valid tag names, it is a part of repository
                    if not re.match(r'[\w][\w.-]{0,127}', sp[1]):
                        sp[0] = sp[0] + ":" + sp[1]
                        sp[1] = "latest"
                elif len(sp) == 3:
                    if re.match(r'[\w][\w.-]{0,127}', sp[2]):
                        sp[0] = sp[0] + ":" + sp[1]
                        sp[1] = sp[2]
                        del sp[2]

                # check for repository:tag match or image id match
                if ((sp[0] == m.group(1) and sp[1] == m.group(2)) or dockerRequirement["dockerImageId"] == m.group(3)):
                    found = True
                    break
            except ValueError:
                pass

        if not found and pull_image:
            cmd = []  # type: List[Text]
            if "dockerPull" in dockerRequirement:
                cmd = ["docker", "pull", str(dockerRequirement["dockerPull"])]
                _logger.info(Text(cmd))
                if not dry_run:
                    subprocess.check_call(cmd, stdout=sys.stderr)
                    found = True
            elif "dockerFile" in dockerRequirement:
                dockerfile_dir = str(tempfile.mkdtemp())
                with open(os.path.join(dockerfile_dir, "Dockerfile"), "wb") as df:
                    df.write(dockerRequirement["dockerFile"].encode('utf-8'))
                cmd = ["docker", "build", "--tag=%s" %
                       str(dockerRequirement["dockerImageId"]), dockerfile_dir]
                _logger.info(Text(cmd))
                if not dry_run:
                    subprocess.check_call(cmd, stdout=sys.stderr)
                    found = True
            elif "dockerLoad" in dockerRequirement:
                cmd = ["docker", "load"]
                _logger.info(Text(cmd))
                if not dry_run:
                    if os.path.exists(dockerRequirement["dockerLoad"]):
                        _logger.info(u"Loading docker image from %s", dockerRequirement["dockerLoad"])
                        with open(dockerRequirement["dockerLoad"], "rb") as f:
                            loadproc = subprocess.Popen(cmd, stdin=f, stdout=sys.stderr)
                    else:
                        loadproc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=sys.stderr)
                        _logger.info(u"Sending GET request to %s", dockerRequirement["dockerLoad"])
                        req = requests.get(dockerRequirement["dockerLoad"], stream=True)
                        n = 0
                        for chunk in req.iter_content(1024 * 1024):
                            n += len(chunk)
                            _logger.info("\r%i bytes" % (n))
                            loadproc.stdin.write(chunk)
                        loadproc.stdin.close()
                    rcode = loadproc.wait()
                    if rcode != 0:
                        raise WorkflowException("Docker load returned non-zero exit status %i" % (rcode))
                    found = True
            elif "dockerImport" in dockerRequirement:
                cmd = ["docker", "import", str(dockerRequirement["dockerImport"]),
                       str(dockerRequirement["dockerImageId"])]
                _logger.info(Text(cmd))
                if not dry_run:
                    subprocess.check_call(cmd, stdout=sys.stderr)
                    found = True

        return found

    def get_from_requirements(self, r, req, pull_image, dry_run=False):
        # type: (Dict[Text, Text], bool, bool, bool) -> Text
        if r:
            errmsg = None
            try:
                subprocess.check_output(["docker", "version"])
            except subprocess.CalledProcessError as e:
                errmsg = "Cannot communicate with docker daemon: " + Text(e)
            except OSError as e:
                errmsg = "'docker' executable not found: " + Text(e)

            if errmsg:
                if req:
                    raise WorkflowException(errmsg)
                else:
                    return None

            if self.get_image(r, pull_image, dry_run):
                return r["dockerImageId"]
            else:
                if req:
                    raise WorkflowException(u"Docker image %s not found" % r["dockerImageId"])

        return None

    def add_volumes(self, pathmapper, runtime):
        # type: (PathMapper, List[Text]) -> None

        host_outdir = self.outdir
        container_outdir = self.builder.outdir
        for src, vol in pathmapper.items():
            if not vol.staged:
                continue
            if vol.target.startswith(container_outdir+"/"):
                host_outdir_tgt = os.path.join(
                    host_outdir, vol.target[len(container_outdir)+1:])
            else:
                host_outdir_tgt = None
            if vol.type in ("File", "Directory"):
                if not vol.resolved.startswith("_:"):
                    runtime.append(u"--volume=%s:%s:ro" % (
                        docker_windows_path_adjust(vol.resolved),
                        docker_windows_path_adjust(vol.target)))
            elif vol.type == "WritableFile":
                if self.inplace_update:
                    runtime.append(u"--volume=%s:%s:rw" % (
                        docker_windows_path_adjust(vol.resolved),
                        docker_windows_path_adjust(vol.target)))
                else:
                    shutil.copy(vol.resolved, host_outdir_tgt)
                    ensure_writable(host_outdir_tgt)
            elif vol.type == "WritableDirectory":
                if vol.resolved.startswith("_:"):
                    os.makedirs(host_outdir_tgt, 0o0755)
                else:
                    if self.inplace_update:
                        runtime.append(u"--volume=%s:%s:rw" % (
                            docker_windows_path_adjust(vol.resolved),
                            docker_windows_path_adjust(vol.target)))
                    else:
                        shutil.copytree(vol.resolved, host_outdir_tgt)
                        ensure_writable(host_outdir_tgt)
            elif vol.type == "CreateFile":
                if host_outdir_tgt:
                    with open(host_outdir_tgt, "wb") as f:
                        f.write(vol.resolved.encode("utf-8"))
                else:
                    fd, createtmp = tempfile.mkstemp(dir=self.tmpdir)
                    with os.fdopen(fd, "wb") as f:
                        f.write(vol.resolved.encode("utf-8"))
                    runtime.append(u"--volume=%s:%s:rw" % (
                        docker_windows_path_adjust(createtmp),
                        docker_windows_path_adjust(vol.target)))

    def create_runtime(self, env, rm_container=True, record_container_id=False, cidfile_dir="",
                       cidfile_prefix="", **kwargs):
        # type: (MutableMapping[Text, Text], bool, bool, Text, Text, **Any) -> List
        user_space_docker_cmd = kwargs.get("user_space_docker_cmd")
        if user_space_docker_cmd:
            runtime = [user_space_docker_cmd, u"run"]
        else:
            runtime = [u"docker", u"run", u"-i"]

        runtime.append(u"--volume=%s:%s:rw" % (
            docker_windows_path_adjust(os.path.realpath(self.outdir)),
            self.builder.outdir))
        runtime.append(u"--volume=%s:%s:rw" % (
            docker_windows_path_adjust(os.path.realpath(self.tmpdir)), "/tmp"))

        self.add_volumes(self.pathmapper, runtime)
        if self.generatemapper:
            self.add_volumes(self.generatemapper, runtime)

        if user_space_docker_cmd:
            runtime = [x.replace(":ro", "") for x in runtime]
            runtime = [x.replace(":rw", "") for x in runtime]

        runtime.append(u"--workdir=%s" % (
            docker_windows_path_adjust(self.builder.outdir)))
        if not user_space_docker_cmd:

            if not kwargs.get("no_read_only"):
                runtime.append(u"--read-only=true")

            if kwargs.get("custom_net", None) is not None:
                runtime.append(u"--net={0}".format(kwargs.get("custom_net")))
            elif kwargs.get("disable_net", None):
                runtime.append(u"--net=none")

            if self.stdout:
                runtime.append("--log-driver=none")

            euid, egid = docker_vm_id()
            if not onWindows():
                # MS Windows does not have getuid() or geteuid() functions
                euid, egid = euid or os.geteuid(), egid or os.getgid()

            if kwargs.get("no_match_user", None) is False \
                    and (euid, egid) != (None, None):
                runtime.append(u"--user=%d:%d" % (euid, egid))

        if rm_container:
            runtime.append(u"--rm")

        runtime.append(u"--env=TMPDIR=/tmp")

        # spec currently says "HOME must be set to the designated output
        # directory." but spec might change to designated temp directory.
        # runtime.append("--env=HOME=/tmp")
        runtime.append(u"--env=HOME=%s" % self.builder.outdir)

        # add parameters to docker to write a container ID file
        if record_container_id:
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
            if cidfile_prefix != "":
                cidfile_name = str(cidfile_prefix + "-" + cidfile_name)
            cidfile_path = os.path.join(cidfile_dir, cidfile_name)
            runtime.append(u"--cidfile=%s" % cidfile_path)

        for t, v in self.environment.items():
            runtime.append(u"--env=%s=%s" % (t, v))

        return runtime
