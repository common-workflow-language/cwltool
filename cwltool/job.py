from __future__ import absolute_import
import codecs
import functools
import io
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from io import open
from typing import (IO, Any, Callable, Dict, Iterable, List, MutableMapping, Text,
                    Tuple, Union, cast)

import shellescape

from .utils import copytree_with_merge, docker_windows_path_adjust, onWindows
from . import docker
from .builder import Builder
from .docker_id import docker_vm_id
from .errors import WorkflowException
from .pathmapper import PathMapper, ensure_writable
from .process import (UnsupportedRequirement, empty_subtree, get_feature,
                      stageFiles)
from .utils import bytes2str_in_dicts

_logger = logging.getLogger("cwltool")

needs_shell_quoting_re = re.compile(r"""(^$|[\s|&;()<>\'"$@])""")

FORCE_SHELLED_POPEN = os.getenv("CWLTOOL_FORCE_SHELL_POPEN", "0") == "1"

SHELL_COMMAND_TEMPLATE = """#!/bin/bash
python "run_job.py" "job.json"
"""

PYTHON_RUN_SCRIPT = """
import json
import os
import sys
import subprocess

with open(sys.argv[1], "r") as f:
    popen_description = json.load(f)
    commands = popen_description["commands"]
    cwd = popen_description["cwd"]
    env = popen_description["env"]
    env["PATH"] = os.environ.get("PATH")
    stdin_path = popen_description["stdin_path"]
    stdout_path = popen_description["stdout_path"]
    stderr_path = popen_description["stderr_path"]
    if stdin_path is not None:
        stdin = open(stdin_path, "rb")
    else:
        stdin = subprocess.PIPE
    if stdout_path is not None:
        stdout = open(stdout_path, "wb")
    else:
        stdout = sys.stderr
    if stderr_path is not None:
        stderr = open(stderr_path, "wb")
    else:
        stderr = sys.stderr
    sp = subprocess.Popen(commands,
                          shell=False,
                          close_fds=True,
                          stdin=stdin,
                          stdout=stdout,
                          stderr=stderr,
                          env=env,
                          cwd=cwd)
    if sp.stdin:
        sp.stdin.close()
    rcode = sp.wait()
    if stdin is not subprocess.PIPE:
        stdin.close()
    if stdout is not sys.stderr:
        stdout.close()
    if stderr is not sys.stderr:
        stderr.close()
    sys.exit(rcode)
"""


def deref_links(outputs):  # type: (Any) -> None
    if isinstance(outputs, dict):
        if outputs.get("class") == "File":
            st = os.lstat(outputs["path"])
            if stat.S_ISLNK(st.st_mode):
                outputs["basename"] = os.path.basename(outputs["path"])
                outputs["path"] = os.readlink(outputs["path"])
        else:
            for v in outputs.values():
                deref_links(v)
    if isinstance(outputs, list):
        for v in outputs:
            deref_links(v)

def relink_initialworkdir(pathmapper, host_outdir, container_outdir, inplace_update=False):
    # type: (PathMapper, Text, Text, bool) -> None
    for src, vol in pathmapper.items():
        if not vol.staged:
            continue

        if vol.type in ("File", "Directory") or (inplace_update and
                                                 vol.type in ("WritableFile", "WritableDirectory")):
            host_outdir_tgt = os.path.join(host_outdir, vol.target[len(container_outdir)+1:])
            if os.path.islink(host_outdir_tgt) or os.path.isfile(host_outdir_tgt):
                os.remove(host_outdir_tgt)
            elif os.path.isdir(host_outdir_tgt):
                shutil.rmtree(host_outdir_tgt)
            if onWindows():
                if vol.type in ("File", "WritableFile"):
                    shutil.copy(vol.resolved, host_outdir_tgt)
                elif vol.type in ("Directory", "WritableDirectory"):
                    copytree_with_merge(vol.resolved, host_outdir_tgt)
            else:
                os.symlink(vol.resolved, host_outdir_tgt)

class JobBase(object):
    def __init__(self):  # type: () -> None
        self.builder = None  # type: Builder
        self.joborder = None  # type: Dict[Text, Union[Dict[Text, Any], List, Text]]
        self.stdin = None  # type: Text
        self.stderr = None  # type: Text
        self.stdout = None  # type: Text
        self.successCodes = None  # type: Iterable[int]
        self.temporaryFailCodes = None  # type: Iterable[int]
        self.permanentFailCodes = None  # type: Iterable[int]
        self.requirements = None  # type: List[Dict[Text, Text]]
        self.hints = None  # type: Dict[Text,Text]
        self.name = None  # type: Text
        self.command_line = None  # type: List[Text]
        self.pathmapper = None  # type: PathMapper
        self.make_pathmapper = None  # type: Callable[..., PathMapper]
        self.generatemapper = None  # type: PathMapper
        self.collect_outputs = None  # type: Union[Callable[[Any], Any], functools.partial[Any]]
        self.output_callback = None  # type: Callable[[Any, Any], Any]
        self.outdir = None  # type: Text
        self.tmpdir = None  # type: Text
        self.environment = None  # type: MutableMapping[Text, Text]
        self.generatefiles = None  # type: Dict[Text, Union[List[Dict[Text, Text]], Dict[Text, Text], Text]]
        self.stagedir = None  # type: Text
        self.inplace_update = None  # type: bool

    def _setup(self, kwargs):  # type: (Dict) -> None
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)

        for knownfile in self.pathmapper.files():
            p = self.pathmapper.mapper(knownfile)
            if p.type == "File" and not os.path.isfile(p[0]) and p.staged:
                raise WorkflowException(
                    u"Input file %s (at %s) not found or is not a regular "
                    "file." % (knownfile, self.pathmapper.mapper(knownfile)[0]))

        if self.generatefiles["listing"]:
            make_path_mapper_kwargs = kwargs
            if "basedir" in make_path_mapper_kwargs:
                make_path_mapper_kwargs = make_path_mapper_kwargs.copy()
                del make_path_mapper_kwargs["basedir"]
            self.generatemapper = self.make_pathmapper(cast(List[Any], self.generatefiles["listing"]),
                                                       self.builder.outdir, basedir=self.outdir, separateDirs=False, **make_path_mapper_kwargs)
            _logger.debug(u"[job %s] initial work dir %s", self.name,
                          json.dumps({p: self.generatemapper.mapper(p) for p in self.generatemapper.files()}, indent=4))

    def _execute(self, runtime, env, rm_tmpdir=True, move_outputs="move"):
        # type: (List[Text], MutableMapping[Text, Text], bool, Text) -> None

        scr, _ = get_feature(self, "ShellCommandRequirement")

        shouldquote = None  # type: Callable[[Any], Any]
        if scr:
            shouldquote = lambda x: False
        else:
            shouldquote = needs_shell_quoting_re.search

        _logger.info(u"[job %s] %s$ %s%s%s%s",
                     self.name,
                     self.outdir,
                     " \\\n    ".join([shellescape.quote(Text(arg)) if shouldquote(Text(arg)) else Text(arg) for arg in
                                       (runtime + self.command_line)]),
                     u' < %s' % self.stdin if self.stdin else '',
                     u' > %s' % os.path.join(self.outdir, self.stdout) if self.stdout else '',
                     u' 2> %s' % os.path.join(self.outdir, self.stderr) if self.stderr else '')

        outputs = {}  # type: Dict[Text,Text]

        try:
            stdin_path = None
            if self.stdin:
                stdin_path = self.pathmapper.reversemap(self.stdin)[1]

            stderr_path = None
            if self.stderr:
                abserr = os.path.join(self.outdir, self.stderr)
                dnerr = os.path.dirname(abserr)
                if dnerr and not os.path.exists(dnerr):
                    os.makedirs(dnerr)
                stderr_path = abserr

            stdout_path = None
            if self.stdout:
                absout = os.path.join(self.outdir, self.stdout)
                dn = os.path.dirname(absout)
                if dn and not os.path.exists(dn):
                    os.makedirs(dn)
                stdout_path = absout

            commands = [Text(x) for x in (runtime + self.command_line)]
            job_script_contents = None  # type: Text
            builder = getattr(self, "builder", None)  # type: Builder
            if builder is not None:
                job_script_contents = builder.build_job_script(commands)
            rcode = _job_popen(
                commands,
                stdin_path=stdin_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                env=env,
                cwd=self.outdir,
                job_script_contents=job_script_contents,
            )

            if self.successCodes and rcode in self.successCodes:
                processStatus = "success"
            elif self.temporaryFailCodes and rcode in self.temporaryFailCodes:
                processStatus = "temporaryFail"
            elif self.permanentFailCodes and rcode in self.permanentFailCodes:
                processStatus = "permanentFail"
            elif rcode == 0:
                processStatus = "success"
            else:
                processStatus = "permanentFail"

            if self.generatefiles["listing"]:
                relink_initialworkdir(self.generatemapper, self.outdir, self.builder.outdir, inplace_update=self.inplace_update)

            outputs = self.collect_outputs(self.outdir)
            outputs = bytes2str_in_dicts(outputs)  # type: ignore

        except OSError as e:
            if e.errno == 2:
                if runtime:
                    _logger.error(u"'%s' not found", runtime[0])
                else:
                    _logger.error(u"'%s' not found", self.command_line[0])
            else:
                _logger.exception("Exception while running job")
            processStatus = "permanentFail"
        except WorkflowException as e:
            _logger.error(u"[job %s] Job error:\n%s" % (self.name, e))
            processStatus = "permanentFail"
        except Exception as e:
            _logger.exception("Exception while running job")
            processStatus = "permanentFail"

        if processStatus != "success":
            _logger.warning(u"[job %s] completed %s", self.name, processStatus)
        else:
            _logger.info(u"[job %s] completed %s", self.name, processStatus)

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(u"[job %s] %s", self.name, json.dumps(outputs, indent=4))

        self.output_callback(outputs, processStatus)

        if self.stagedir and os.path.exists(self.stagedir):
            _logger.debug(u"[job %s] Removing input staging directory %s", self.name, self.stagedir)
            shutil.rmtree(self.stagedir, True)

        if rm_tmpdir:
            _logger.debug(u"[job %s] Removing temporary directory %s", self.name, self.tmpdir)
            shutil.rmtree(self.tmpdir, True)


class CommandLineJob(JobBase):

    def run(self, pull_image=True, rm_container=True,
            rm_tmpdir=True, move_outputs="move", **kwargs):
        # type: (bool, bool, bool, Text, **Any) -> None

        self._setup(kwargs)

        env = self.environment
        if not os.path.exists(self.tmpdir):
            os.makedirs(self.tmpdir)
        vars_to_preserve = kwargs.get("preserve_environment")
        if kwargs.get("preserve_entire_environment"):
            vars_to_preserve = os.environ
        if vars_to_preserve is not None:
            for key, value in os.environ.items():
                if key in vars_to_preserve and key not in env:
                    # On Windows, subprocess env can't handle unicode.
                    env[key] = str(value) if onWindows() else value
        env["HOME"] = str(self.outdir) if onWindows() else self.outdir
        env["TMPDIR"] = str(self.tmpdir) if onWindows() else self.tmpdir
        if "PATH" not in env:
            env["PATH"] = str(os.environ["PATH"]) if onWindows() else os.environ["PATH"]
        if "SYSTEMROOT" not in env and "SYSTEMROOT" in os.environ:
            env["SYSTEMROOT"] = str(os.environ["SYSTEMROOT"]) if onWindows() else os.environ["SYSTEMROOT"]

        stageFiles(self.pathmapper, ignoreWritable=True, symLink=True)
        if self.generatemapper:
            stageFiles(self.generatemapper, ignoreWritable=self.inplace_update, symLink=True)
            relink_initialworkdir(self.generatemapper, self.outdir, self.builder.outdir, inplace_update=self.inplace_update)

        self._execute([], env, rm_tmpdir=rm_tmpdir, move_outputs=move_outputs)


class DockerCommandLineJob(JobBase):

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

    def run(self, pull_image=True, rm_container=True,
            rm_tmpdir=True, move_outputs="move", **kwargs):
        # type: (bool, bool, bool, Text, **Any) -> None

        (docker_req, docker_is_req) = get_feature(self, "DockerRequirement")

        img_id = None
        env = None  # type: MutableMapping[Text, Text]
        user_space_docker_cmd = kwargs.get("user_space_docker_cmd")
        if docker_req and user_space_docker_cmd:
            # For user-space docker implementations, a local image name or ID
            # takes precedence over a network pull
            if 'dockerImageId' in docker_req:
                img_id = str(docker_req["dockerImageId"])
            elif 'dockerPull' in docker_req:
                img_id = str(docker_req["dockerPull"])
            else:
                raise Exception("Docker image must be specified as "
                        "'dockerImageId' or 'dockerPull' when using user "
                        "space implementations of Docker")
        else:
            try:
                env = cast(MutableMapping[Text, Text], os.environ)
                if docker_req and kwargs.get("use_container"):
                    img_id = str(docker.get_from_requirements(
                        docker_req, True, pull_image))
                if img_id is None:
                    if self.builder.find_default_container:
                        default_container = self.builder.find_default_container()
                        if default_container:
                            img_id = str(default_container)
                            env = cast(MutableMapping[Text, Text], os.environ)

                if docker_req and img_id is None and kwargs.get("use_container"):
                    raise Exception("Docker image not available")
            except Exception as e:
                _logger.debug("Docker error", exc_info=True)
                if docker_is_req:
                    raise UnsupportedRequirement(
                        "Docker is required to run this tool: %s" % e)
                else:
                    raise WorkflowException(
                        "Docker is not available for this tool, try "
                        "--no-container to disable Docker, or install "
                        "a user space Docker replacement like uDocker with "
                        "--user-space-docker-cmd.: %s" % e)

        self._setup(kwargs)

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

        for t, v in self.environment.items():
            runtime.append(u"--env=%s=%s" % (t, v))

        runtime.append(img_id)

        self._execute(
            runtime, env, rm_tmpdir=rm_tmpdir, move_outputs=move_outputs)


def _job_popen(
        commands,  # type: List[Text]
        stdin_path,  # type: Text
        stdout_path,  # type: Text
        stderr_path,  # type: Text
        env,  # type: Union[MutableMapping[Text, Text], MutableMapping[str, str]]
        cwd,  # type: Text
        job_dir=None,  # type: Text
        job_script_contents=None,  # type: Text
):
    # type: (...) -> int
    if not job_script_contents and not FORCE_SHELLED_POPEN:

        stdin = None  # type: Union[IO[Any], int]
        stderr = None  # type: IO[Any]
        stdout = None  # type: IO[Any]

        if stdin_path is not None:
            stdin = open(stdin_path, "rb")
        else:
            stdin = subprocess.PIPE

        if stdout_path is not None:
            stdout = open(stdout_path, "wb")
        else:
            stdout = sys.stderr

        if stderr_path is not None:
            stderr = open(stderr_path, "wb")
        else:
            stderr = sys.stderr

        sp = subprocess.Popen(commands,
                              shell=False,
                              close_fds=not onWindows(),
                              stdin=stdin,
                              stdout=stdout,
                              stderr=stderr,
                              env=env,
                              cwd=cwd)

        if sp.stdin:
            sp.stdin.close()

        rcode = sp.wait()

        if isinstance(stdin, io.IOBase):
            stdin.close()

        if stdout is not sys.stderr:
            stdout.close()

        if stderr is not sys.stderr:
            stderr.close()

        return rcode
    else:
        if job_dir is None:
            job_dir = tempfile.mkdtemp(prefix="cwltooljob")

        if not job_script_contents:
            job_script_contents = SHELL_COMMAND_TEMPLATE

        env_copy = {}
        key = None  # type: Any
        for key in env:
            env_copy[key] = env[key]

        job_description = dict(
            commands=commands,
            cwd=cwd,
            env=env_copy,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            stdin_path=stdin_path,
        )
        with open(os.path.join(job_dir, "job.json"), "wb") as f:
            json.dump(job_description, codecs.getwriter('utf-8')(f), ensure_ascii=False) # type: ignore
        try:
            job_script = os.path.join(job_dir, "run_job.bash")
            with open(job_script, "wb") as f:
                f.write(job_script_contents.encode('utf-8'))
            job_run = os.path.join(job_dir, "run_job.py")
            with open(job_run, "wb") as f:
                f.write(PYTHON_RUN_SCRIPT.encode('utf-8'))
            sp = subprocess.Popen(
                ["bash", job_script.encode("utf-8")],
                shell=False,
                cwd=job_dir,
                stdout=sys.stderr,  # The nested script will output the paths to the correct files if they need
                stderr=sys.stderr,  # to be captured. Else just write everything to stderr (same as above).
                stdin=subprocess.PIPE,
            )
            if sp.stdin:
                sp.stdin.close()

            rcode = sp.wait()

            return rcode
        finally:
            shutil.rmtree(job_dir)
