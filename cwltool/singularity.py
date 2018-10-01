"""Support for executing Docker containers using a Singularity."""
from __future__ import absolute_import

import os
import os.path
import re
import shutil
import sys
from io import open  # pylint: disable=redefined-builtin
from typing import Dict, List, MutableMapping, Optional

from schema_salad.sourceline import SourceLine
from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .context import RuntimeContext  # pylint: disable=unused-import
from .errors import WorkflowException
from .job import ContainerCommandLineJob
from .loghandler import _logger
from .pathmapper import PathMapper  # pylint: disable=unused-import
from .pathmapper import ensure_writable
from .process import UnsupportedRequirement
from .utils import docker_windows_path_adjust
if os.name == 'posix':
    from subprocess32 import (  # pylint: disable=import-error,no-name-in-module
        check_call, check_output, CalledProcessError, DEVNULL, PIPE, Popen,
        TimeoutExpired)
else:  # we're not on Unix, so none of this matters
    pass

_USERNS = None

def _singularity_supports_userns():  # type: ()->bool
    global _USERNS  # pylint: disable=global-statement
    if _USERNS is None:
        try:
            hello_image = os.path.join(os.path.dirname(__file__), 'hello.simg')
            result = Popen(
                [u"singularity", u"exec", u"--userns", hello_image, u"true"],
                stderr=PIPE, stdout=DEVNULL,
                universal_newlines=True).communicate(timeout=60)[1]
            _USERNS = "No valid /bin/sh" in result
        except TimeoutExpired:
            _USERNS = False
    return _USERNS

def _normalize_image_id(string):  # type: (Text)->Text
    candidate = re.sub(pattern=r'([a-z]*://)', repl=r'', string=string)
    return re.sub(pattern=r'[:/]', repl=r'-', string=candidate) + ".img"


class SingularityCommandLineJob(ContainerCommandLineJob):

    @staticmethod
    def get_image(dockerRequirement,  # type: Dict[Text, Text]
                  pull_image,         # type: bool
                  force_pull=False    # type: bool
                 ):
        # type: (...) -> bool
        """
        Acquire the software container image in the specified dockerRequirement
        using Singularity and returns the success as a bool. Updates the
        provided dockerRequirement with the specific dockerImageId to the full
        path of the local image, if found. Likewise the
        dockerRequirement['dockerPull'] is updated to a docker:// URI if needed.
        """
        found = False

        candidates = []

        if "dockerImageId" not in dockerRequirement and "dockerPull" in dockerRequirement:
            match = re.search(pattern=r'([a-z]*://)', string=dockerRequirement["dockerPull"])
            candidate = _normalize_image_id(dockerRequirement['dockerPull'])
            candidates.append(candidate)
            dockerRequirement['dockerImageId'] = candidate
            if not match:
                dockerRequirement["dockerPull"] = "docker://" + dockerRequirement["dockerPull"]
        elif "dockerImageId" in dockerRequirement:
            candidates.append(dockerRequirement['dockerImageId'])
            candidates.append(_normalize_image_id(dockerRequirement['dockerImageId']))

        # check if Singularity image is available in $SINGULARITY_CACHEDIR
        targets = [os.getcwd()]
        for env in ("SINGULARITY_CACHEDIR", "SINGULARITY_PULLFOLDER"):
            if env in os.environ:
                targets.append(os.environ[env])
        for target in targets:
            for candidate in candidates:
                path = os.path.join(target, candidate)
                if os.path.isfile(path):
                    _logger.info(
                        "Using local copy of Singularity image found in %s",
                        target)
                    dockerRequirement["dockerImageId"] = path
                    found = True

        if (force_pull or not found) and pull_image:
            cmd = []  # type: List[Text]
            if "dockerPull" in dockerRequirement:
                cmd = ["singularity", "pull", "--force", "--name",
                       str(dockerRequirement["dockerImageId"]),
                       str(dockerRequirement["dockerPull"])]
                _logger.info(Text(cmd))
                check_call(cmd, stdout=sys.stderr)
                found = True
            elif "dockerFile" in dockerRequirement:
                raise WorkflowException(SourceLine(
                    dockerRequirement, 'dockerFile').makeError(
                        "dockerFile is not currently supported when using the "
                        "Singularity runtime for Docker containers."))
            elif "dockerLoad" in dockerRequirement:
                raise WorkflowException(SourceLine(
                    dockerRequirement, 'dockerLoad').makeError(
                        "dockerLoad is not currently supported when using the "
                        "Singularity runtime for Docker containers."))
            elif "dockerImport" in dockerRequirement:
                raise WorkflowException(SourceLine(
                    dockerRequirement, 'dockerImport').makeError(
                        "dockerImport is not currently supported when using the "
                        "Singularity runtime for Docker containers."))

        return found

    def get_from_requirements(self,
                              r,                      # type: Optional[Dict[Text, Text]]
                              req,                    # type: bool
                              pull_image,             # type: bool
                              force_pull=False,       # type: bool
                              tmp_outdir_prefix=None  # type: Text
                             ):
        # type: (...) -> Optional[Text]
        """
        Returns the filename of the Singularity image (e.g.
        hello-world-latest.img).
        """

        if r:
            errmsg = None
            try:
                check_output(["singularity", "--version"])
            except CalledProcessError as err:
                errmsg = "Cannot execute 'singularity --version' {}".format(err)
            except OSError as err:
                errmsg = "'singularity' executable not found: {}".format(err)

            if errmsg:
                if req:
                    raise WorkflowException(errmsg)
                else:
                    return None

            if self.get_image(r, pull_image, force_pull):
                return os.path.abspath(r["dockerImageId"])
            if req:
                raise WorkflowException(u"Container image {} not "
                                        "found".format(r["dockerImageId"]))

        return None

    def add_volumes(self, pathmapper, runtime, stage_output):
        # type: (PathMapper, List[Text], bool) -> None

        host_outdir = self.outdir
        host_outdir_tgt = None  # type: Optional[Text]
        container_outdir = self.builder.outdir
        for _, vol in pathmapper.items():
            if not vol.staged:
                continue
            if stage_output and not vol.target.startswith(container_outdir):
                containertgt = container_outdir + vol.target[len(host_outdir):]
            else:
                containertgt = vol.target
            if vol.target.startswith(container_outdir + "/"):
                host_outdir_tgt = os.path.join(
                    host_outdir, vol.target[len(container_outdir) + 1:])
            if vol.type in ("File", "Directory"):

                if not vol.resolved.startswith("_:"):
                    runtime.append(u"--bind")
                    runtime.append("{}:{}:ro".format(
                        docker_windows_path_adjust(vol.resolved),
                        docker_windows_path_adjust(containertgt)))
            elif vol.type == "WritableFile":
                if self.inplace_update:
                    runtime.append(u"--bind")
                    runtime.append(u"{}:{}:rw".format(
                        docker_windows_path_adjust(vol.resolved),
                        docker_windows_path_adjust(containertgt)))
                elif host_outdir_tgt:
                    shutil.copy(vol.resolved, host_outdir_tgt)
                    ensure_writable(host_outdir_tgt)
            elif vol.type == "WritableDirectory":
                if vol.resolved.startswith("_:") and host_outdir_tgt:
                    os.makedirs(host_outdir_tgt, 0o0755)
                else:
                    if self.inplace_update:
                        runtime.append(u"--bind")
                        runtime.append(u"{}:{}:rw".format(
                            docker_windows_path_adjust(vol.resolved),
                            docker_windows_path_adjust(containertgt)))
                    elif host_outdir_tgt:
                        shutil.copytree(vol.resolved, host_outdir_tgt)
            elif vol.type == "CreateFile":
                createtmp = os.path.join(host_outdir, os.path.basename(vol.target))
                with open(createtmp, "wb") as tmp:
                    tmp.write(vol.resolved.encode("utf-8"))
                runtime.append(u"--bind")
                runtime.append(u"{}:{}:ro".format(
                    docker_windows_path_adjust(createtmp),
                    docker_windows_path_adjust(vol.target)))

    def create_runtime(self,
                       env,                        # type: MutableMapping[Text, Text]
                       runtimeContext              # type: RuntimeContext
                      ):
        # type: (...) -> List
        """ Returns the Singularity runtime list of commands and options."""

        runtime = [u"singularity", u"--quiet", u"exec", u"--contain", u"--pid",
                   u"--ipc"]
        if _singularity_supports_userns():
            runtime.append(u"--userns")
        runtime.append(u"--bind")
        runtime.append(u"{}:{}:rw".format(
            docker_windows_path_adjust(os.path.realpath(self.outdir)),
            self.builder.outdir))
        runtime.append(u"--bind")
        runtime.append(u"{}:{}:rw".format(
            docker_windows_path_adjust(os.path.realpath(self.tmpdir)), "/tmp"))

        self.add_volumes(self.pathmapper, runtime, stage_output=False)
        if self.generatemapper:
            self.add_volumes(self.generatemapper, runtime, stage_output=True)

        runtime.append(u"--pwd")
        runtime.append("%s" % (docker_windows_path_adjust(self.builder.outdir)))

        if runtimeContext.custom_net is not None:
            raise UnsupportedRequirement(
                "Singularity implementation does not support custom networking")
        elif runtimeContext.disable_net:
            runtime.append(u"--net")

        env["SINGULARITYENV_TMPDIR"] = "/tmp"
        env["SINGULARITYENV_HOME"] = self.builder.outdir

        for name, value in self.environment.items():
            env["SINGULARITYENV_{}".format(name)] = value
        return runtime
