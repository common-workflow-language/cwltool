from __future__ import absolute_import

import logging
import os
import re
import shutil
import subprocess
import sys
from io import open

from typing import (Dict, List, Text, MutableMapping, Any)

from .errors import WorkflowException
from .job import ContainerCommandLineJob
from .pathmapper import PathMapper, ensure_writable
from .process import (UnsupportedRequirement)
from .utils import docker_windows_path_adjust

_logger = logging.getLogger("cwltool")


class SingularityCommandLineJob(ContainerCommandLineJob):
    @staticmethod
    def get_image(dockerRequirement, pull_image, dry_run=False):
        # type: (Dict[Text, Text], bool, bool) -> bool
        found = False

        if "dockerImageId" not in dockerRequirement and "dockerPull" in dockerRequirement:
            match = re.search(pattern=r'([a-z]*://)', string=dockerRequirement["dockerPull"])
            if match:
                dockerRequirement["dockerImageId"] = re.sub(pattern=r'([a-z]*://)', repl=r'',
                                                            string=dockerRequirement["dockerPull"])
                dockerRequirement["dockerImageId"] = re.sub(pattern=r'[:/]', repl=r'-',
                                                            string=dockerRequirement["dockerImageId"]) + ".img"
            else:
                dockerRequirement["dockerImageId"] = re.sub(pattern=r'[:/]', repl=r'-',
                                                            string=dockerRequirement["dockerPull"]) + ".img"
                dockerRequirement["dockerPull"] = "docker://" + dockerRequirement["dockerPull"]

        # check to see if the Singularity container is already downloaded
        if os.path.isfile(dockerRequirement["dockerImageId"]):
            _logger.info("Using local copy of Singularity image")
            found = True

        # if the .img file is not already present, pull the image
        elif pull_image:
            cmd = []  # type: List[Text]
            if "dockerPull" in dockerRequirement:
                cmd = ["singularity", "pull", "--name", str(dockerRequirement["dockerImageId"]),
                       str(dockerRequirement["dockerPull"])]
                _logger.info(Text(cmd))
                if not dry_run:
                    subprocess.check_call(cmd, stdout=sys.stderr)
                    found = True

        return found

    def get_from_requirements(self, r, req, pull_image, dry_run=False):
        # type: (Dict[Text, Text], bool, bool, bool) -> Text
        # returns the filename of the Singularity image (e.g. hello-world-latest.img)
        if r:
            errmsg = None
            try:
                subprocess.check_output(["singularity", "--version"])
            except subprocess.CalledProcessError as e:
                errmsg = "Cannot execute 'singularity --version' " + Text(e)
            except OSError as e:
                errmsg = "'singularity' executable not found: " + Text(e)

            if errmsg:
                if req:
                    raise WorkflowException(errmsg)
                else:
                    return None

            if self.get_image(r, pull_image, dry_run):
                return os.path.abspath(r["dockerImageId"])
            else:
                if req:
                    raise WorkflowException(u"Container image %s not found" % r["dockerImageId"])

        return None

    def add_volumes(self, pathmapper, runtime, stage_output):
        # type: (PathMapper, List[Text], bool) -> None

        host_outdir = self.outdir
        container_outdir = self.builder.outdir
        for src, vol in pathmapper.items():
            if not vol.staged:
                continue
            if stage_output:
                containertgt = container_outdir + vol.target[len(host_outdir):]
            else:
                containertgt = vol.target
            if vol.target.startswith(container_outdir + "/"):
                host_outdir_tgt = os.path.join(
                    host_outdir, vol.target[len(container_outdir) + 1:])
            else:
                host_outdir_tgt = None
            if vol.type in ("File", "Directory"):
                if not vol.resolved.startswith("_:"):
                    runtime.append(u"--bind")
                    runtime.append("%s:%s:ro" % (
                    docker_windows_path_adjust(vol.resolved), docker_windows_path_adjust(containertgt)))
            elif vol.type == "WritableFile":
                if self.inplace_update:
                    runtime.append(u"--bind")
                    runtime.append("%s:%s:rw" % (
                    docker_windows_path_adjust(vol.resolved), docker_windows_path_adjust(containertgt)))
                else:
                    shutil.copy(vol.resolved, host_outdir_tgt)
                    ensure_writable(host_outdir_tgt)
            elif vol.type == "WritableDirectory":
                if vol.resolved.startswith("_:"):
                    os.makedirs(host_outdir_tgt, 0o0755)
                else:
                    if self.inplace_update:
                        runtime.append(u"--bind")
                        runtime.append("%s:%s:rw" % (
                        docker_windows_path_adjust(vol.resolved), docker_windows_path_adjust(containertgt)))
                    else:
                        shutil.copytree(vol.resolved, vol.target)
            elif vol.type == "CreateFile":
                createtmp = os.path.join(host_outdir, os.path.basename(vol.target))
                with open(createtmp, "wb") as f:
                    f.write(vol.resolved.encode("utf-8"))
                runtime.append(u"--bind")
                runtime.append(
                    "%s:%s:ro" % (docker_windows_path_adjust(createtmp), docker_windows_path_adjust(vol.target)))

    def create_runtime(self, env, rm_container=True, record_container_id=False, cidfile_dir="",
                       cidfile_prefix="", **kwargs):
        # type: (MutableMapping[Text, Text], bool, bool, Text, Text, **Any) -> List

        runtime = [u"singularity", u"--quiet", u"exec"]
        runtime.append(u"--bind")
        runtime.append(
            u"%s:%s:rw" % (docker_windows_path_adjust(os.path.realpath(self.outdir)), self.builder.outdir))
        runtime.append(u"--bind")
        runtime.append(u"%s:%s:rw" % (docker_windows_path_adjust(os.path.realpath(self.tmpdir)), "/tmp"))

        self.add_volumes(self.pathmapper, runtime, stage_output=False)
        if self.generatemapper:
            self.add_volumes(self.generatemapper, runtime, stage_output=True)

        runtime.append(u"--pwd")
        runtime.append("%s" % (docker_windows_path_adjust(self.builder.outdir)))

        if kwargs.get("custom_net", None) is not None:
            raise UnsupportedRequirement(
                "Singularity implementation does not support networking")

        env["SINGULARITYENV_TMPDIR"] = "/tmp"
        env["SINGULARITYENV_HOME"] = self.builder.outdir

        for t, v in self.environment.items():
            env["SINGULARITYENV_" + t] = v
        return runtime
