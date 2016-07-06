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
from .docker_uid import docker_vm_uid
from .builder import Builder
from typing import Union, Iterable, Callable, Any, Mapping, IO, cast, Tuple
from .pathmapper import PathMapper
import functools

_logger = logging.getLogger("cwltool")

needs_shell_quoting_re = re.compile(r"""(^$|[\s|&;()<>\'"$@])""")

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
        self.joborder = None  # type: Dict[unicode, Union[Dict[unicode, Any], List, unicode]]
        self.stdin = None  # type: str
        self.stderr = None  # type: str
        self.stdout = None  # type: str
        self.successCodes = None  # type: Iterable[int]
        self.temporaryFailCodes = None  # type: Iterable[int]
        self.permanentFailCodes = None  # type: Iterable[int]
        self.requirements = None  # type: List[Dict[str, str]]
        self.hints = None  # type: Dict[str,str]
        self.name = None  # type: unicode
        self.command_line = None  # type: List[unicode]
        self.pathmapper = None  # type: PathMapper
        self.collect_outputs = None  # type: Union[Callable[[Any], Any],functools.partial[Any]]
        self.output_callback = None  # type: Callable[[Any, Any], Any]
        self.outdir = None  # type: str
        self.tmpdir = None  # type: str
        self.environment = None  # type: Dict[str,str]
        self.generatefiles = None  # type: Dict[unicode, Union[List[Dict[str, str]], Dict[str,str], str]] 
        self.stagedir = None  # type: unicode

    def run(self, dry_run=False, pull_image=True, rm_container=True,
            rm_tmpdir=True, move_outputs="move", **kwargs):
        # type: (bool, bool, bool, bool, bool, unicode, **Any) -> Union[Tuple[str,Dict[None,None]],None]
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)

        #with open(os.path.join(outdir, "cwl.input.json"), "w") as fp:
        #    json.dump(self.joborder, fp)

        runtime = []  # type: List[unicode]

        # spec currently says "HOME must be set to the designated output
        # directory." but spec might change to designated temp directory.
        # env = {"TMPDIR": self.tmpdir, "HOME": self.tmpdir}  # type: Mapping[str,str]
        env = {"TMPDIR": self.tmpdir, "HOME": self.outdir}  # type: Mapping[str,str]

        (docker_req, docker_is_req) = get_feature(self, "DockerRequirement")

        for knownfile in self.pathmapper.files():
            p = self.pathmapper.mapper(knownfile)
            if p.type == "File" and not os.path.isfile(p[0]):
                raise WorkflowException(
                u"Input file %s (at %s) not found or is not a regular file."
                % (knownfile, self.pathmapper.mapper(knownfile)[0]))

        img_id = None
        if docker_req and kwargs.get("use_container") is not False:
            env = os.environ
            img_id = docker.get_from_requirements(docker_req, docker_is_req, pull_image)

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
            runtime.append(u"--volume=%s:%s:rw" % (os.path.abspath(self.outdir), "/var/spool/cwl"))
            runtime.append(u"--volume=%s:%s:rw" % (os.path.abspath(self.tmpdir), "/tmp"))
            runtime.append(u"--workdir=%s" % ("/var/spool/cwl"))
            runtime.append("--read-only=true")
            if (kwargs.get("enable_net", None) is None and
                    kwargs.get("custom_net", None) is not None):
                runtime.append("--net=none")
            elif kwargs.get("custom_net", None) is not None:
                runtime.append("--net={0}".format(kwargs.get("custom_net")))

            if self.stdout:
                runtime.append("--log-driver=none")

            euid = docker_vm_uid() or os.geteuid()
            runtime.append(u"--user=%s" % (euid))

            if rm_container:
                runtime.append("--rm")

            runtime.append("--env=TMPDIR=/tmp")

            # spec currently says "HOME must be set to the designated output
            # directory." but spec might change to designated temp directory.
            # runtime.append("--env=HOME=/tmp")
            runtime.append("--env=HOME=/var/spool/cwl")

            for t,v in self.environment.items():
                runtime.append(u"--env=%s=%s" % (t, v))

            runtime.append(img_id)
        else:
            env = self.environment
            if not os.path.exists(self.tmpdir):
                os.makedirs(self.tmpdir)
            env["TMPDIR"] = self.tmpdir
            vars_to_preserve = kwargs.get("preserve_environment")
            if vars_to_preserve is not None:
                for key, value in os.environ.items():
                    if key in vars_to_preserve and key not in env:
                        env[key] = value

            stageFiles(self.pathmapper, os.symlink)

        stdin = None  # type: Union[IO[Any],int]
        stderr = None  # type: IO[Any]
        stdout = None  # type: IO[Any]

        scr, _ = get_feature(self, "ShellCommandRequirement")

        if scr:
            shouldquote = lambda x: False
        else:
            shouldquote = needs_shell_quoting_re.search

        _logger.info(u"[job %s] %s$ %s%s%s%s",
                     self.name,
                     self.outdir,
                     " \\\n    ".join([shellescape.quote(str(arg)) if shouldquote(str(arg)) else str(arg) for arg in (runtime + self.command_line)]),
                     u' < %s' % self.stdin if self.stdin else '',
                     u' > %s' % os.path.join(self.outdir, self.stdout) if self.stdout else '',
                     u' 2> %s' % os.path.join(self.outdir, self.stderr) if self.stderr else '')

        if dry_run:
            return (self.outdir, {})

        outputs = {}  # type: Dict[str,str]

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

            if self.stdin:
                stdin = open(self.pathmapper.reversemap(self.stdin)[1], "rb")
            else:
                stdin = subprocess.PIPE

            if self.stderr:
                abserr = os.path.join(self.outdir, self.stderr)
                dnerr = os.path.dirname(abserr)
                if dnerr and not os.path.exists(dnerr):
                    os.makedirs(dnerr)
                stderr = open(abserr, "wb")
            else:
                stderr = sys.stderr

            if self.stdout:
                absout = os.path.join(self.outdir, self.stdout)
                dn = os.path.dirname(absout)
                if dn and not os.path.exists(dn):
                    os.makedirs(dn)
                stdout = open(absout, "wb")
            else:
                stdout = sys.stderr

            sp = subprocess.Popen([unicode(x).encode('utf-8') for x in runtime + self.command_line],
                                  shell=False,
                                  close_fds=True,
                                  stdin=stdin,
                                  stderr=stderr,
                                  stdout=stdout,
                                  env=env,
                                  cwd=self.outdir)

            if sp.stdin:
                sp.stdin.close()

            rcode = sp.wait()

            if isinstance(stdin, file):
                stdin.close()

            if stderr is not sys.stderr:
                stderr.close()

            if stdout is not sys.stderr:
                stdout.close()

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
                    if os.path.exists(tgt) and os.path.islink(tgt):
                        os.remove(tgt)
                        os.symlink(src, tgt)
                stageFiles(generatemapper, linkoutdir)

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
            _logger.error(u"Error while running job: %s" % e)
            processStatus = "permanentFail"
        except Exception as e:
            _logger.exception("Exception while running job")
            processStatus = "permanentFail"

        if processStatus != "success":
            _logger.warn(u"[job %s] completed %s", self.name, processStatus)
        else:
            _logger.debug(u"[job %s] completed %s", self.name, processStatus)
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
