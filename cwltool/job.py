import subprocess
import io
import os
import tempfile
import glob
import json
import logging
import sys
import requests
from . import docker
from .process import get_feature, empty_subtree, stageFiles
from .errors import WorkflowException
import shutil
import stat
import re
import shellescape
import string
from .docker_uid import docker_vm_uid
from .builder import Builder
from typing import (Any, Callable, Union, Iterable, Mapping, MutableMapping,
        IO, cast, Text, Tuple)
from .pathmapper import PathMapper
import functools

_logger = logging.getLogger("cwltool")

needs_shell_quoting_re = re.compile(r"""(^$|[\s|&;()<>\'"$@])""")

FORCE_SHELLED_POPEN = os.getenv("CWLTOOL_FORCE_SHELL_POPEN", "0") == "1"

SHELL_COMMAND_TEMPLATE = """#!/bin/bash
python "run_job.py" "job.json"
"""

PYTHON_RUN_SCRIPT = """
import json
import sys
import subprocess

with open(sys.argv[1], "r") as f:
    popen_description = json.load(f)
    commands = popen_description["commands"]
    cwd = popen_description["cwd"]
    env = popen_description["env"]
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
    if isinstance(stdin, file):
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
                outputs["path"] = os.readlink(outputs["path"])
        else:
            for v in outputs.values():
                deref_links(v)
    if isinstance(outputs, list):
        for v in outputs:
            deref_links(v)

class CommandLineJob(object):

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
        self.collect_outputs = None  # type: Union[Callable[[Any], Any], functools.partial[Any]]
        self.output_callback = None  # type: Callable[[Any, Any], Any]
        self.outdir = None  # type: Text
        self.tmpdir = None  # type: Text
        self.environment = None  # type: MutableMapping[Text, Text]
        self.generatefiles = None  # type: Dict[Text, Union[List[Dict[Text, Text]], Dict[Text, Text], Text]]
        self.stagedir = None  # type: Text

    def run(self, dry_run=False, pull_image=True, rm_container=True,
            rm_tmpdir=True, move_outputs="move", **kwargs):
        # type: (bool, bool, bool, bool, Text, **Any) -> Union[Tuple[Text, Dict[None, None]], None]
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)

        #with open(os.path.join(outdir, "cwl.input.json"), "w") as fp:
        #    json.dump(self.joborder, fp)

        runtime = []  # type: List[Text]

        (docker_req, docker_is_req) = get_feature(self, "DockerRequirement")

        for knownfile in self.pathmapper.files():
            p = self.pathmapper.mapper(knownfile)
            if p.type == "File" and not os.path.isfile(p[0]):
                raise WorkflowException(
                    u"Input file %s (at %s) not found or is not a regular "
                    "file." % (knownfile, self.pathmapper.mapper(knownfile)[0]))

        img_id = None
        env = None  # type: Union[MutableMapping[Text, Text], MutableMapping[str, str]]
        if docker_req and kwargs.get("use_container") is not False:
            env = os.environ
            img_id = docker.get_from_requirements(docker_req, docker_is_req, pull_image)
        elif kwargs.get("default_container", None) is not None:
            env = os.environ
            img_id = kwargs.get("default_container")

        if docker_is_req and img_id is None:
            raise WorkflowException("Docker is required for running this tool.")

        if img_id:
            runtime = ["docker", "run", "-i"]
            for src in self.pathmapper.files():
                vol = self.pathmapper.mapper(src)
                if vol.type == "File":
                    runtime.append(u"--volume=%s:%s:ro" % (vol.resolved, vol.target))
                if vol.type == "CreateFile":
                    createtmp = os.path.join(self.stagedir, os.path.basename(vol.target))
                    with open(createtmp, "w") as f:
                        f.write(vol.resolved.encode("utf-8"))
                    runtime.append(u"--volume=%s:%s:ro" % (createtmp, vol.target))
            runtime.append(u"--volume=%s:%s:rw" % (os.path.realpath(self.outdir), self.builder.outdir))
            runtime.append(u"--volume=%s:%s:rw" % (os.path.realpath(self.tmpdir), "/tmp"))
            runtime.append(u"--workdir=%s" % (self.builder.outdir))
            runtime.append("--read-only=true")

            if kwargs.get("custom_net", None) is not None:
                runtime.append("--net={0}".format(kwargs.get("custom_net")))
            elif kwargs.get("disable_net", None):
                runtime.append("--net=none")

            if self.stdout:
                runtime.append("--log-driver=none")

            euid = docker_vm_uid() or os.geteuid()

            if kwargs.get("no_match_user",None) is False:
                runtime.append(u"--user=%s" % (euid))

            if rm_container:
                runtime.append("--rm")

            runtime.append("--env=TMPDIR=/tmp")

            # spec currently says "HOME must be set to the designated output
            # directory." but spec might change to designated temp directory.
            # runtime.append("--env=HOME=/tmp")
            runtime.append("--env=HOME=%s" % self.builder.outdir)

            for t,v in self.environment.items():
                runtime.append(u"--env=%s=%s" % (t, v))

            runtime.append(img_id)
        else:
            env = self.environment
            if not os.path.exists(self.tmpdir):
                os.makedirs(self.tmpdir)
            vars_to_preserve = kwargs.get("preserve_environment")
            if kwargs.get("preserve_entire_environment"):
                vars_to_preserve = os.environ
            if vars_to_preserve is not None:
                for key, value in os.environ.items():
                    if key in vars_to_preserve and key not in env:
                        env[key] = value
            env["HOME"] = self.outdir
            env["TMPDIR"] = self.tmpdir

            stageFiles(self.pathmapper, os.symlink)

        scr, _ = get_feature(self, "ShellCommandRequirement")

        if scr:
            shouldquote = lambda x: False
        else:
            shouldquote = needs_shell_quoting_re.search

        _logger.info(u"[job %s] %s$ %s%s%s%s",
                     self.name,
                     self.outdir,
                     " \\\n    ".join([shellescape.quote(Text(arg)) if shouldquote(Text(arg)) else Text(arg) for arg in (runtime + self.command_line)]),
                     u' < %s' % self.stdin if self.stdin else '',
                     u' > %s' % os.path.join(self.outdir, self.stdout) if self.stdout else '',
                     u' 2> %s' % os.path.join(self.outdir, self.stderr) if self.stderr else '')

        if dry_run:
            return (self.outdir, {})

        outputs = {}  # type: Dict[Text,Text]

        try:
            if self.generatefiles["listing"]:
                generatemapper = PathMapper([self.generatefiles], self.outdir,
                                            self.outdir, separateDirs=False)
                _logger.debug(u"[job %s] initial work dir %s", self.name,
                              json.dumps({p: generatemapper.mapper(p) for p in generatemapper.files()}, indent=4))

                def linkoutdir(src, tgt):
                    # Need to make the link to the staged file (may be inside
                    # the container)
                    for _, item in self.pathmapper.items():
                        if src == item.resolved:
                            os.symlink(item.target, tgt)
                            break
                stageFiles(generatemapper, linkoutdir)

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

            build_job_script = self.builder.build_job_script  # type: Callable[[List[str]], Text]
            rcode = _job_popen(
                [Text(x).encode('utf-8') for x in runtime + self.command_line],
                stdin_path=stdin_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                env=env,
                cwd=self.outdir,
                build_job_script=build_job_script,
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
                def linkoutdir(src, tgt):
                    # Need to make the link to the staged file (may be inside
                    # the container)
                    if os.path.islink(tgt):
                        os.remove(tgt)
                        os.symlink(src, tgt)
                stageFiles(generatemapper, linkoutdir, ignoreWritable=True)

            outputs = self.collect_outputs(self.outdir)

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
            _logger.warn(u"[job %s] completed %s", self.name, processStatus)
        else:
            _logger.debug(u"[job %s] completed %s", self.name, processStatus)

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(u"[job %s] %s", self.name, json.dumps(outputs, indent=4))

        self.output_callback(outputs, processStatus)

        if self.stagedir and os.path.exists(self.stagedir):
            _logger.debug(u"[job %s] Removing input staging directory %s", self.name, self.stagedir)
            shutil.rmtree(self.stagedir, True)

        if rm_tmpdir:
            _logger.debug(u"[job %s] Removing temporary directory %s", self.name, self.tmpdir)
            shutil.rmtree(self.tmpdir, True)

        if move_outputs == "move" and empty_subtree(self.outdir):
            _logger.debug(u"[job %s] Removing empty output directory %s", self.name, self.outdir)
            shutil.rmtree(self.outdir, True)


def _job_popen(
    commands,  # type: List[str]
    stdin_path,  # type: Text
    stdout_path,  # type: Text
    stderr_path,  # type: Text
    env,  # type: Union[MutableMapping[Text, Text], MutableMapping[str, str]]
    cwd,  # type: Text
    job_dir=None,  # type: Text
    build_job_script=None,  # type: Callable[[List[str]], Text]
):
    # type: (...) -> int

    job_script_contents = None  # type: Text
    if build_job_script:
        job_script_contents = build_job_script(commands)

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
                              close_fds=True,
                              stdin=stdin,
                              stdout=stdout,
                              stderr=stderr,
                              env=env,
                              cwd=cwd)

        if sp.stdin:
            sp.stdin.close()

        rcode = sp.wait()

        if isinstance(stdin, file):
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
        for key in env:
            key = key.encode("utf-8")
            env_copy[key] = env[key]

        job_description = dict(
            commands=commands,
            cwd=cwd,
            env=env_copy,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            stdin_path=stdin_path,
        )
        with open(os.path.join(job_dir, "job.json"), "w") as f:
            json.dump(job_description, f)
        try:
            job_script = os.path.join(job_dir, "run_job.bash")
            with open(job_script, "w") as f:
                f.write(job_script_contents)
            job_run = os.path.join(job_dir, "run_job.py")
            with open(job_run, "w") as f:
                f.write(PYTHON_RUN_SCRIPT)
            sp = subprocess.Popen(
                ["bash", job_script.encode("utf-8")],
                shell=False,
                cwd=job_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
            )
            if sp.stdin:
                sp.stdin.close()

            rcode = sp.wait()

            return rcode
        finally:
            shutil.rmtree(job_dir)
