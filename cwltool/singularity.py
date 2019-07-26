"""Support for executing Docker containers using the Singularity 2.x engine."""
from __future__ import absolute_import

import os
import os.path
import re
import shutil
import tempfile
import sys
from distutils import spawn
from io import open  # pylint: disable=redefined-builtin
from typing import Dict, List, MutableMapping, Optional, Tuple

from schema_salad.sourceline import SourceLine
from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .context import RuntimeContext  # pylint: disable=unused-import
from .errors import WorkflowException
from .job import ContainerCommandLineJob
from .loghandler import _logger
from .pathmapper import PathMapper, MapperEnt  # pylint: disable=unused-import
from .pathmapper import ensure_writable, ensure_non_writable
from .process import UnsupportedRequirement
from .utils import docker_windows_path_adjust

if os.name == 'posix':
    if sys.version_info < (3, 5):
        from subprocess32 import (  # nosec # pylint: disable=import-error,no-name-in-module
            check_call, check_output, CalledProcessError, DEVNULL, PIPE, Popen,
            TimeoutExpired)
    else:
        from subprocess import (  # nosec # pylint: disable=import-error,no-name-in-module
            check_call, check_output, CalledProcessError, DEVNULL, PIPE, Popen,
            TimeoutExpired)

else:  # we're not on Unix, so none of this matters
    pass

_USERNS = None
_SINGULARITY_VERSION = None

def _singularity_supports_userns():  # type: ()->bool
    global _USERNS  # pylint: disable=global-statement
    if _USERNS is None:
        try:
            hello_image = os.path.join(os.path.dirname(__file__), 'hello.simg')
            result = Popen(  # nosec
                [u"singularity", u"exec", u"--userns", hello_image, u"true"],
                stderr=PIPE, stdout=DEVNULL,
                universal_newlines=True).communicate(timeout=60)[1]
            _USERNS = "No valid /bin/sh" in result
        except TimeoutExpired:
            _USERNS = False
    return _USERNS


def get_version():  # type: ()->Text
    global _SINGULARITY_VERSION  # pylint: disable=global-statement
    if not _SINGULARITY_VERSION:
       _SINGULARITY_VERSION = check_output(["singularity", "--version"], universal_newlines=True)
       if _SINGULARITY_VERSION.startswith("singularity version "):
           _SINGULARITY_VERSION = _SINGULARITY_VERSION[20:]
    return _SINGULARITY_VERSION

def is_version_2_6():  # type: ()->bool
    return get_version().startswith("2.6")

def is_version_3_or_newer():  # type: ()->bool
    return int(get_version()[0]) >= 3

def is_version_3_1_or_newer():  # type: ()->bool
    version = get_version().split('.')
    return int(version[0]) >= 4 or (int(version[0]) == 3 and int(version[1]) >= 1)

def _normalize_image_id(string):  # type: (Text)->Text
    return string.replace('/', '_') + '.img'

def _normalize_sif_id(string): # type: (Text)->Text
    return string.replace('/', '_') + '.sif'

class SingularityCommandLineJob(ContainerCommandLineJob):

    @staticmethod
    def get_image(dockerRequirement,  # type: Dict[Text, Text]
                  pull_image,         # type: bool
                  force_pull=False    # type: bool
                 ):
        # type: (...) -> bool
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
        if "CWL_SINGULARITY_CACHE" in os.environ:
            cache_folder = os.environ["CWL_SINGULARITY_CACHE"]
        elif is_version_2_6() and "SINGULARITY_PULLFOLDER" in os.environ:
            cache_folder = os.environ["SINGULARITY_PULLFOLDER"]

        if "dockerImageId" not in dockerRequirement and "dockerPull" in dockerRequirement:
            match = re.search(pattern=r'([a-z]*://)', string=dockerRequirement["dockerPull"])
            img_name = _normalize_image_id(dockerRequirement['dockerPull'])
            candidates.append(img_name)
            if is_version_3_or_newer():
                sif_name = _normalize_sif_id(dockerRequirement['dockerPull'])
                candidates.append(sif_name)
                dockerRequirement["dockerImageId"] = sif_name
            else:
                dockerRequirement["dockerImageId"] = img_name
            if not match:
                dockerRequirement["dockerPull"] = "docker://" + dockerRequirement["dockerPull"]
        elif "dockerImageId" in dockerRequirement:
            candidates.append(dockerRequirement['dockerImageId'])
            candidates.append(_normalize_image_id(dockerRequirement['dockerImageId']))
            if is_version_3_or_newer():
                candidates.append(_normalize_sif_id(dockerRequirement['dockerPull']))

        targets = [os.getcwd()]
        if "CWL_SINGULARITY_CACHE" in os.environ:
            targets.append(os.environ["CWL_SINGULARITY_CACHE"])
        if is_version_2_6() and "SINGULARITY_PULLFOLDER" in os.environ:
            targets.append(os.environ["SINGULARITY_PULLFOLDER"])
        for target in targets:
            for dirpath, subdirs, files in os.walk(target):
                for entry in files:
                    if entry in candidates:
                        path = os.path.join(dirpath, entry)
                        if os.path.isfile(path):
                            _logger.info(
                                "Using local copy of Singularity image found in %s",
                                dirpath)
                            dockerRequirement["dockerImageId"] = path
                            found = True
        if (force_pull or not found) and pull_image:
            cmd = []  # type: List[Text]
            if "dockerPull" in dockerRequirement:
                if cache_folder:
                    env = os.environ.copy()
                    if is_version_2_6():
                        env['SINGULARITY_PULLFOLDER'] = cache_folder
                        cmd = ["singularity", "pull", "--force", "--name",
                               dockerRequirement["dockerImageId"],
                               str(dockerRequirement["dockerPull"])]
                    else:
                        cmd = ["singularity", "pull", "--force", "--name",
                               "{}/{}".format(
                                   cache_folder,
                                   dockerRequirement["dockerImageId"]),
                               str(dockerRequirement["dockerPull"])]

                    _logger.info(Text(cmd))
                    check_call(cmd, env=env, stdout=sys.stderr)  # nosec
                    dockerRequirement["dockerImageId"] = '{}/{}'.format(
                            cache_folder, dockerRequirement["dockerImageId"])
                    found = True
                else:
                    cmd = ["singularity", "pull", "--force", "--name",
                           str(dockerRequirement["dockerImageId"]),
                           str(dockerRequirement["dockerPull"])]
                    _logger.info(Text(cmd))
                    check_call(cmd, stdout=sys.stderr)  # nosec
                    found = True

            elif "dockerFile" in dockerRequirement:
                raise WorkflowException(SourceLine(
                    dockerRequirement, 'dockerFile').makeError(
                        "dockerFile is not currently supported when using the "
                        "Singularity runtime for Docker containers."))
            elif "dockerLoad" in dockerRequirement:
                if is_version_3_1_or_newer():
                    if 'dockerImageId' in dockerRequirement:
                        name = "{}.sif".format(dockerRequirement["dockerImageId"])
                    else:
                        name = "{}.sif".format(dockerRequirement["dockerLoad"])
                    cmd = ["singularity", "build", name,
                         "docker-archive://{}".format(dockerRequirement["dockerLoad"])]
                    _logger.info(Text(cmd))
                    check_call(cmd, stdout=sys.stderr)  # nosec
                    found = True
                    dockerRequirement['dockerImageId'] = name
                raise WorkflowException(SourceLine(
                    dockerRequirement, 'dockerLoad').makeError(
                        "dockerLoad is not currently supported when using the "
                        "Singularity runtime (version less than 3.1) for Docker containers."))
            elif "dockerImport" in dockerRequirement:
                raise WorkflowException(SourceLine(
                    dockerRequirement, 'dockerImport').makeError(
                        "dockerImport is not currently supported when using the "
                        "Singularity runtime for Docker containers."))

        return found

    def get_from_requirements(self,
                              r,                      # type: Dict[Text, Text]
                              pull_image,             # type: bool
                              force_pull=False,       # type: bool
                              tmp_outdir_prefix=None  # type: Text
                             ):
        # type: (...) -> Optional[Text]
        """
        Return the filename of the Singularity image.

        (e.g. hello-world-latest.{img,sif}).
        """
        if not bool(spawn.find_executable('singularity')):
            raise WorkflowException('singularity executable is not available')

        if not self.get_image(r, pull_image, force_pull):
            raise WorkflowException(u"Container image {} not "
                                    "found".format(r["dockerImageId"]))

        return os.path.abspath(r["dockerImageId"])

    @staticmethod
    def append_volume(runtime, source, target, writable=False):
        # type: (List[Text], Text, Text, bool) -> None
        runtime.append(u"--bind")
        runtime.append("{}:{}:{}".format(
            docker_windows_path_adjust(source),
            docker_windows_path_adjust(target), "rw" if writable else "ro"))

    def add_file_or_directory_volume(self,
                                     runtime,         # type: List[Text]
                                     volume,          # type: MapperEnt
                                     host_outdir_tgt  # type: Optional[Text]
                                    ):  # type: (...) -> None
        if host_outdir_tgt is not None:
            # workaround for lack of overlapping mounts in Singularity
            # revert to daa923d5b0be3819b6ed0e6440e7193e65141052
            # once https://github.com/sylabs/singularity/issues/1607
            # is fixed
            if volume.type == "File":
                shutil.copy(volume.resolved, host_outdir_tgt)
            else:
                shutil.copytree(volume.resolved, host_outdir_tgt)
            ensure_non_writable(host_outdir_tgt)
        elif not volume.resolved.startswith("_:"):
            self.append_volume(runtime, volume.resolved, volume.target)

    def add_writable_file_volume(self,
                                 runtime,          # type: List[Text]
                                 volume,           # type: MapperEnt
                                 host_outdir_tgt,  # type: Optional[Text]
                                 tmpdir_prefix     # type: Text
                                ):  # type: (...) -> None
        if host_outdir_tgt is not None:
            # workaround for lack of overlapping mounts in Singularity
            # revert to daa923d5b0be3819b6ed0e6440e7193e65141052
            # once https://github.com/sylabs/singularity/issues/1607
            # is fixed
            if self.inplace_update:
                try:
                    os.link(os.path.realpath(volume.resolved),
                            host_outdir_tgt)
                except os.error:
                    shutil.copy(volume.resolved, host_outdir_tgt)
            else:
                shutil.copy(volume.resolved, host_outdir_tgt)
            ensure_writable(host_outdir_tgt)
        elif self.inplace_update:
            self.append_volume(
                runtime, volume.resolved, volume.target, writable=True)
            ensure_writable(volume.resolved)
        else:
            tmp_dir, tmp_prefix = os.path.split(tmpdir_prefix)
            file_copy = os.path.join(
                tempfile.mkdtemp(prefix=tmp_prefix, dir=tmp_dir),
                os.path.basename(volume.resolved))
            shutil.copy(volume.resolved, file_copy)
            #volume.resolved = file_copy
            self.append_volume(
                runtime, file_copy, volume.target, writable=True)
            ensure_writable(file_copy)

    def add_writable_directory_volume(self,
                                      runtime,          # type: List[Text]
                                      volume,           # type: MapperEnt
                                      host_outdir_tgt,  # type: Optional[Text]
                                      tmpdir_prefix     # type: Text
                                     ):  # type: (...) -> None
        if volume.resolved.startswith("_:"):
            if host_outdir_tgt is not None:
                new_dir = host_outdir_tgt
            else:
                tmp_dir, tmp_prefix = os.path.split(tmpdir_prefix)
                new_dir = os.path.join(
                    tempfile.mkdtemp(prefix=tmp_prefix, dir=tmp_dir),
                    os.path.basename(volume.resolved))
            os.makedirs(new_dir)
        else:
            if host_outdir_tgt is not None:
                # workaround for lack of overlapping mounts in Singularity
                # revert to daa923d5b0be3819b6ed0e6440e7193e65141052
                # once https://github.com/sylabs/singularity/issues/1607
                # is fixed
                shutil.copytree(volume.resolved, host_outdir_tgt)
                ensure_writable(host_outdir_tgt)
            else:
                if not self.inplace_update:
                    tmp_dir, tmp_prefix = os.path.split(tmpdir_prefix)
                    dir_copy = os.path.join(
                        tempfile.mkdtemp(prefix=tmp_prefix, dir=tmp_dir),
                        os.path.basename(volume.resolved))
                    shutil.copytree(volume.resolved, dir_copy)
                    source = dir_copy
                    #volume.resolved = dir_copy
                else:
                    source = volume.resolved
                self.append_volume(
                    runtime, source, volume.target, writable=True)
                ensure_writable(source)


    def create_runtime(self,
                       env,              # type: MutableMapping[Text, Text]
                       runtime_context   # type: RuntimeContext
                      ):  # type: (...) -> Tuple[List, Optional[Text]]
        """Return the Singularity runtime list of commands and options."""
        any_path_okay = self.builder.get_requirement("DockerRequirement")[1] \
            or False
        runtime = [u"singularity", u"--quiet", u"exec", u"--contain", u"--pid",
                   u"--ipc"]
        if _singularity_supports_userns():
            runtime.append(u"--userns")
        if is_version_3_1_or_newer():
            runtime.append(u"--home")
            runtime.append(u"{}:{}".format(
                docker_windows_path_adjust(os.path.realpath(self.outdir)),
                self.builder.outdir))
        else:
            runtime.append(u"--bind")
            runtime.append(u"{}:{}:rw".format(
                docker_windows_path_adjust(os.path.realpath(self.outdir)),
                self.builder.outdir))
        runtime.append(u"--bind")
        tmpdir = "/tmp"  # nosec
        runtime.append(u"{}:{}:rw".format(
            docker_windows_path_adjust(os.path.realpath(self.tmpdir)), tmpdir))

        self.add_volumes(self.pathmapper, runtime, any_path_okay=True,
                         secret_store=runtime_context.secret_store,
                         tmpdir_prefix=runtime_context.tmpdir_prefix)
        if self.generatemapper is not None:
            self.add_volumes(
                self.generatemapper, runtime, any_path_okay=any_path_okay,
                secret_store=runtime_context.secret_store,
                tmpdir_prefix=runtime_context.tmpdir_prefix)

        runtime.append(u"--pwd")
        runtime.append(u"%s" % (docker_windows_path_adjust(self.builder.outdir)))


        if runtime_context.custom_net:
            raise UnsupportedRequirement(
                "Singularity implementation does not support custom networking")
        elif runtime_context.disable_net:
            runtime.append(u"--net")

        env["SINGULARITYENV_TMPDIR"] = tmpdir
        env["SINGULARITYENV_HOME"] = self.builder.outdir

        for name, value in self.environment.items():
            env["SINGULARITYENV_{}".format(name)] = str(value)
        return (runtime, None)

