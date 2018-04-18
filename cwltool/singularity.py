"""Support for executing Docker containers using Singularity."""
from __future__ import absolute_import
import logging
import os
import re
import shutil
import sys
from io import open  # pylint: disable=redefined-builtin
from typing import (Dict, List, Text, Optional, MutableMapping)
from .errors import WorkflowException
from .job import ContainerCommandLineJob
from .pathmapper import PathMapper, ensure_writable
from .process import (UnsupportedRequirement)
from .utils import docker_windows_path_adjust
if os.name == 'posix' and sys.version_info[0] < 3:
    from subprocess32 import (check_call, check_output,  # pylint: disable=import-error
                              CalledProcessError, DEVNULL, PIPE, Popen,
                              TimeoutExpired)
elif os.name == 'posix':
    from subprocess import (check_call, check_output,  # type: ignore
                            CalledProcessError, DEVNULL, PIPE, Popen,
                            TimeoutExpired)
else:  # we're not on Unix, so none of this matters
    pass

_logger = logging.getLogger("cwltool")
_USERNS = None

def _singularity_supports_userns():  # type: ()->bool
    global _USERNS  # pylint: disable=global-statement
    if _USERNS is None:
        try:
            _USERNS = "No valid /bin/sh" in Popen(
                [u"singularity", u"exec", u"--userns", u"/etc", u"true"],
                stderr=PIPE, stdout=DEVNULL).communicate(timeout=60)[1]
        except TimeoutExpired:
            _USERNS = False
    return _USERNS


class SingularityCommandLineJob(ContainerCommandLineJob):
    @staticmethod
    def get_image(dockerRequirement,  # type: Dict[Text, Text]
                  pull_image,         # type: bool
                  dry_run=False       # type: bool
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

        if "dockerImageId" not in dockerRequirement and "dockerPull" in dockerRequirement:
            match = re.search(pattern=r'([a-z]*://)', string=dockerRequirement["dockerPull"])
            if match:
                dockerRequirement["dockerImageId"] = re.sub(pattern=r'([a-z]*://)', repl=r'',
                                                            string=dockerRequirement["dockerPull"])
                dockerRequirement["dockerImageId"] = re.sub(
                    pattern=r'[:/]', repl=r'-', string=dockerRequirement["dockerImageId"]) + ".img"
            else:
                dockerRequirement["dockerImageId"] = re.sub(
                    pattern=r'[:/]', repl=r'-', string=dockerRequirement["dockerPull"]) + ".img"
                dockerRequirement["dockerPull"] = "docker://" + dockerRequirement["dockerPull"]

        # check if Singularity image is available in $SINGULARITY_CACHEDIR
        if "SINGULARITY_CACHEDIR" in os.environ and os.path.isfile(
                os.path.join(os.environ["SINGULARITY_CACHEDIR"],
                             dockerRequirement["dockerImageId"])):
            _logger.info("Using local copy of Singularity image found in "
                         "$SINGULARITY_CACHEDIR")
            dockerRequirement["dockerImageId"] = os.path.join(
                os.environ["SINGULARITY_CACHEDIR"],
                dockerRequirement["dockerImageId"])
            found = True

        # check if Singularity image is available in $SINGULARITY_PULLFOLDER
        elif "SINGULARITY_PULLFOLDER" in os.environ and os.path.isfile(
                os.path.join(os.environ["SINGULARITY_PULLFOLDER"],
                             dockerRequirement["dockerImageId"])):
            _logger.info("Using local copy of Singularity image found in "
                         "$SINGULARITY_PULLFOLDER")
            dockerRequirement["dockerImageId"] = os.path.join(
                os.environ["SINGULARITY_PULLFOLDER"],
                dockerRequirement["dockerImageId"])
            found = True

        # check if Singularity image is available in current working directory
        elif os.path.isfile(dockerRequirement["dockerImageId"]):
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
                    check_call(cmd, stdout=sys.stderr)
                    found = True

        return found

    def get_from_requirements(self,
                              r,                # type: Optional[Dict[Text, Text]]
                              req,              # type: bool
                              pull_image,       # type: bool
                              dry_run=False,    # type: bool
                              force_pull=False  # type: bool
                             ):
        # type: (...) -> Text
        """
        Returns the filename of the Singularity image (e.g.
        hello-world-latest.img).
        """

        if force_pull:
            _logger.warning("--force-docker-pull currently not supported for "
                            "singularity")

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

            if self.get_image(r, pull_image, dry_run):
                return os.path.abspath(r["dockerImageId"])
            else:
                if req:
                    raise WorkflowException(u"Container image {} not "
                                            "found".format(r["dockerImageId"]))

        return None

    def add_volumes(self, pathmapper, runtime, stage_output):
        # type: (PathMapper, List[Text], bool) -> None

        host_outdir = self.outdir
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
            else:
                host_outdir_tgt = None
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
                else:
                    shutil.copy(vol.resolved, host_outdir_tgt)
                    ensure_writable(host_outdir_tgt)
            elif vol.type == "WritableDirectory":
                if vol.resolved.startswith("_:"):
                    os.makedirs(host_outdir_tgt, 0o0755)
                else:
                    if self.inplace_update:
                        runtime.append(u"--bind")
                        runtime.append(u"{}:{}:rw".format(
                            docker_windows_path_adjust(vol.resolved),
                            docker_windows_path_adjust(containertgt)))
                    else:
                        shutil.copytree(vol.resolved, vol.target)
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
                       rm_container=True,          # type: bool
                       record_container_id=False,  # type: bool
                       cidfile_dir="",             # type: Text
                       cidfile_prefix="",          # type: Text
                       **kwargs
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

        if kwargs.get("custom_net", None) is not None:
            raise UnsupportedRequirement(
                "Singularity implementation does not support custom networking")
        elif kwargs.get("disable_net", None):
            runtime.append(u"--net")

        env["SINGULARITYENV_TMPDIR"] = "/tmp"
        env["SINGULARITYENV_HOME"] = self.builder.outdir

        for name, value in self.environment.items():
            env["SINGULARITYENV_{}".format(name)] = value
        return runtime
