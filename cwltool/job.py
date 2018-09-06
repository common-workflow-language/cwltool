from __future__ import absolute_import

import datetime
import functools  # pylint: disable=unused-import
import logging
import os
import re
import shutil
import stat
import sys
import tempfile
import uuid
from abc import ABCMeta, abstractmethod
from io import IOBase, open  # pylint: disable=redefined-builtin
from threading import Timer
from typing import (IO, Any, AnyStr, Callable, Dict, Iterable, List,
                    MutableMapping, MutableSequence, Optional, Union, cast)

import shellescape
from prov.model import PROV
from schema_salad.sourceline import SourceLine
from six import PY2, with_metaclass
from typing_extensions import (TYPE_CHECKING,  # pylint: disable=unused-import
                               Text)
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .builder import Builder, HasReqsHints  # pylint: disable=unused-import
from .context import RuntimeContext  # pylint: disable=unused-import
from .context import getdefault
from .errors import WorkflowException
from .loghandler import _logger
from .pathmapper import PathMapper
from .process import UnsupportedRequirement, stageFiles
from .secrets import SecretStore  # pylint: disable=unused-import
from .utils import \
    bytes2str_in_dicts  # pylint: disable=unused-import; pylint: disable=unused-import
from .utils import (DEFAULT_TMP_PREFIX, Directory, copytree_with_merge,
                    json_dump, json_dumps, onWindows, processes_to_kill,
                    subprocess)

if TYPE_CHECKING:
    from .provenance import CreateProvProfile  # pylint: disable=unused-import
needs_shell_quoting_re = re.compile(r"""(^$|[\s|&;()<>\'"$@])""")

FORCE_SHELLED_POPEN = os.getenv("CWLTOOL_FORCE_SHELL_POPEN", "0") == "1"

SHELL_COMMAND_TEMPLATE = u"""#!/bin/bash
python "run_job.py" "job.json"
"""

PYTHON_RUN_SCRIPT = u"""
import json
import os
import sys
if os.name == 'posix':
    try:
        import subprocess32 as subprocess  # type: ignore
    except Exception:
        import subprocess
else:
    import subprocess  # type: ignore

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
    if os.name == 'nt':
        close_fds = False
        for key, value in env.items():
            env[key] = str(value)
    else:
        close_fds = True
    sp = subprocess.Popen(commands,
                          shell=False,
                          close_fds=close_fds,
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
    if isinstance(outputs, MutableMapping):
        if outputs.get("class") == "File":
            st = os.lstat(outputs["path"])
            if stat.S_ISLNK(st.st_mode):
                outputs["basename"] = os.path.basename(outputs["path"])
                outputs["path"] = os.readlink(outputs["path"])
        else:
            for v in outputs.values():
                deref_links(v)
    if isinstance(outputs, MutableSequence):
        for output in outputs:
            deref_links(output)

def relink_initialworkdir(pathmapper, host_outdir, container_outdir, inplace_update=False):
    # type: (PathMapper, Text, Text, bool) -> None
    for _, vol in pathmapper.items():
        if not vol.staged:
            continue

        if vol.type in ("File", "Directory") or (inplace_update and
                                                 vol.type in ("WritableFile", "WritableDirectory")):
            host_outdir_tgt = os.path.join(host_outdir, vol.target[len(container_outdir)+1:])
            if os.path.islink(host_outdir_tgt) or os.path.isfile(host_outdir_tgt):
                os.remove(host_outdir_tgt)
            elif os.path.isdir(host_outdir_tgt) and not vol.resolved.startswith("_:"):
                shutil.rmtree(host_outdir_tgt)
            if onWindows():
                if vol.type in ("File", "WritableFile"):
                    shutil.copy(vol.resolved, host_outdir_tgt)
                elif vol.type in ("Directory", "WritableDirectory"):
                    copytree_with_merge(vol.resolved, host_outdir_tgt)
            elif not vol.resolved.startswith("_:"):
                os.symlink(vol.resolved, host_outdir_tgt)

class JobBase(with_metaclass(ABCMeta, HasReqsHints)):
    def __init__(self,
                 builder,   # type: Builder
                 joborder,  # type: Dict[Text, Union[Dict[Text, Any], List, Text, None]]
                 make_path_mapper,  # type: Callable[..., PathMapper]
                 requirements,  # type: List[Dict[Text, Text]]
                 hints,  # type: List[Dict[Text, Text]]
                 name,   # type: Text
                ):  # type: (...) -> None
        self.builder = builder
        self.joborder = joborder
        self.stdin = None  # type: Optional[Text]
        self.stderr = None  # type: Optional[Text]
        self.stdout = None  # type: Optional[Text]
        self.successCodes = None  # type: Optional[Iterable[int]]
        self.temporaryFailCodes = None  # type: Optional[Iterable[int]]
        self.permanentFailCodes = None  # type: Optional[Iterable[int]]
        self.requirements = requirements
        self.hints = hints
        self.name = name
        self.command_line = []  # type: List[Text]
        self.pathmapper = PathMapper([], u"", u"")
        self.make_path_mapper = make_path_mapper
        self.generatemapper = None  # type: Optional[PathMapper]

        # set in CommandLineTool.job(i)
        self.collect_outputs = cast(Callable[[Any], Any], None)  # type: Union[Callable[[Any], Any], functools.partial[Any]]
        self.output_callback = cast(Callable[[Any, Any], Any], None)
        self.outdir = u""
        self.tmpdir = u""

        self.environment = {}  # type: MutableMapping[Text, Text]
        self.generatefiles = {"class": "Directory", "listing": [], "basename": ""}  # type: Directory
        self.stagedir = None  # type: Optional[Text]
        self.inplace_update = False
        self.prov_obj = None   # type: Optional[CreateProvProfile]
        self.parent_wf = None  # type: Optional[CreateProvProfile]
        self.timelimit = None  # type: Optional[int]
        self.networkaccess = False  # type: bool

    @abstractmethod
    def run(self,
            runtimeContext  # type: RuntimeContext
           ):  # type: (...) -> None
        pass

    def _setup(self, runtimeContext):  # type: (RuntimeContext) -> None
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)

        for knownfile in self.pathmapper.files():
            p = self.pathmapper.mapper(knownfile)
            if p.type == "File" and not os.path.isfile(p[0]) and p.staged:
                raise WorkflowException(
                    u"Input file %s (at %s) not found or is not a regular "
                    "file." % (knownfile, self.pathmapper.mapper(knownfile)[0]))

        if self.generatefiles["listing"]:
            runtimeContext = runtimeContext.copy()
            runtimeContext.outdir = self.outdir
            self.generatemapper = self.make_path_mapper(
                cast(List[Any], self.generatefiles["listing"]),
                self.builder.outdir, runtimeContext, False)
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(
                    u"[job %s] initial work dir %s", self.name,
                    json_dumps({p: self.generatemapper.mapper(p)
                                for p in self.generatemapper.files()}, indent=4))

    def _execute(self,
                 runtime,                # type: List[Text]
                 env,                    # type: MutableMapping[Text, Text]
                 runtimeContext          # type: RuntimeContext
                ):  # type: (...) -> None

        scr, _ = self.get_requirement("ShellCommandRequirement")

        shouldquote = needs_shell_quoting_re.search   # type: Callable[[Any], Any]
        if scr:
            shouldquote = lambda x: False

        _logger.info(u"[job %s] %s$ %s%s%s%s",
                     self.name,
                     self.outdir,
                     " \\\n    ".join([shellescape.quote(Text(arg)) if shouldquote(Text(arg)) else Text(arg) for arg in
                                       (runtime + self.command_line)]),
                     u' < %s' % self.stdin if self.stdin else '',
                     u' > %s' % os.path.join(self.outdir, self.stdout) if self.stdout else '',
                     u' 2> %s' % os.path.join(self.outdir, self.stderr) if self.stderr else '')
        if self.joborder and runtimeContext.research_obj:
            job_order = self.joborder
            assert runtimeContext.prov_obj
            assert runtimeContext.process_run_id
            runtimeContext.prov_obj.used_artefacts(
                job_order, runtimeContext.process_run_id, str(self.name))
        outputs = {}  # type: Dict[Text,Text]
        try:
            stdin_path = None
            if self.stdin:
                rmap = self.pathmapper.reversemap(self.stdin)
                if not rmap:
                    raise WorkflowException(
                        "{} missing from pathmapper".format(self.stdin))
                else:
                    stdin_path = rmap[1]


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
                dnout = os.path.dirname(absout)
                if dnout and not os.path.exists(dnout):
                    os.makedirs(dnout)
                stdout_path = absout

            commands = [Text(x) for x in runtime + self.command_line]
            if runtimeContext.secret_store:
                commands = runtimeContext.secret_store.retrieve(commands)
                env = runtimeContext.secret_store.retrieve(env)

            job_script_contents = None  # type: Optional[Text]
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
                job_dir=tempfile.mkdtemp(prefix=getdefault(runtimeContext.tmp_outdir_prefix, DEFAULT_TMP_PREFIX)),
                job_script_contents=job_script_contents,
                timelimit=self.timelimit,
                name=self.name
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
                assert self.generatemapper is not None
                relink_initialworkdir(
                    self.generatemapper, self.outdir, self.builder.outdir,
                    inplace_update=self.inplace_update)

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
        except WorkflowException as err:
            _logger.error(u"[job %s] Job error:\n%s", self.name, err)
            processStatus = "permanentFail"
        except Exception as e:
            _logger.exception("Exception while running job")
            processStatus = "permanentFail"
        if runtimeContext.research_obj and self.prov_obj and \
                runtimeContext.process_run_id:
            #creating entities for the outputs produced by each step (in the provenance document)
            self.prov_obj.generate_output_prov(
                outputs, runtimeContext.process_run_id, str(self.name))
            self.prov_obj.document.wasEndedBy(
                runtimeContext.process_run_id, None, self.prov_obj.workflow_run_uri,
                datetime.datetime.now())
        if processStatus != "success":
            _logger.warning(u"[job %s] completed %s", self.name, processStatus)
        else:
            _logger.info(u"[job %s] completed %s", self.name, processStatus)

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(u"[job %s] %s", self.name,
                          json_dumps(outputs, indent=4))

        if self.generatemapper and runtimeContext.secret_store:
            # Delete any runtime-generated files containing secrets.
            for f, p in self.generatemapper.items():
                if p.type == "CreateFile":
                    if runtimeContext.secret_store.has_secret(p.resolved):
                        host_outdir = self.outdir
                        container_outdir = self.builder.outdir
                        host_outdir_tgt = p.target
                        if p.target.startswith(container_outdir+"/"):
                            host_outdir_tgt = os.path.join(
                                host_outdir, p.target[len(container_outdir)+1:])
                        os.remove(host_outdir_tgt)

        if runtimeContext.workflow_eval_lock is None:
            raise WorkflowException("runtimeContext.workflow_eval_lock must not be None")

        with runtimeContext.workflow_eval_lock:
            self.output_callback(outputs, processStatus)

        if self.stagedir and os.path.exists(self.stagedir):
            _logger.debug(u"[job %s] Removing input staging directory %s", self.name, self.stagedir)
            shutil.rmtree(self.stagedir, True)

        if runtimeContext.rm_tmpdir:
            _logger.debug(u"[job %s] Removing temporary directory %s", self.name, self.tmpdir)
            shutil.rmtree(self.tmpdir, True)


class CommandLineJob(JobBase):

    def run(self,
            runtimeContext     # type: RuntimeContext
           ):  # type: (...) -> None

        if not os.path.exists(self.tmpdir):
            os.makedirs(self.tmpdir)
        self._setup(runtimeContext)

        env = self.environment
        vars_to_preserve = runtimeContext.preserve_environment
        if runtimeContext.preserve_entire_environment:
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

        stageFiles(self.pathmapper, ignoreWritable=True, symLink=True, secret_store=runtimeContext.secret_store)
        if self.generatemapper:
            stageFiles(self.generatemapper, ignoreWritable=self.inplace_update,
                       symLink=True, secret_store=runtimeContext.secret_store)
            relink_initialworkdir(self.generatemapper, self.outdir,
                                  self.builder.outdir, inplace_update=self.inplace_update)

        self._execute([], env, runtimeContext)


class ContainerCommandLineJob(with_metaclass(ABCMeta, JobBase)):
    '''
    Commandline job using containers
    '''

    @abstractmethod
    def get_from_requirements(self,
                              r,                      # type: Dict[Text, Text]
                              req,                    # type: bool
                              pull_image,             # type: bool
                              force_pull=False,       # type: bool
                              tmp_outdir_prefix=DEFAULT_TMP_PREFIX  # type: Text
                             ):  # type: (...) -> Optional[Text]
        pass

    @abstractmethod
    def create_runtime(self, env, runtimeContext):
        # type: (MutableMapping[Text, Text], RuntimeContext) -> List
        """ Return the list of commands to run the selected container engine."""
        pass

    def run(self, runtimeContext):
        # type: (RuntimeContext) -> None
        if not os.path.exists(self.tmpdir):
            os.makedirs(self.tmpdir)
        (docker_req, docker_is_req) = self.get_requirement("DockerRequirement")
        self.prov_obj = runtimeContext.prov_obj
        img_id = None
        env = cast(MutableMapping[Text, Text], os.environ)
        user_space_docker_cmd = runtimeContext.user_space_docker_cmd
        if docker_req and user_space_docker_cmd:
            # For user-space docker implementations, a local image name or ID
            # takes precedence over a network pull
            if 'dockerImageId' in docker_req:
                img_id = str(docker_req["dockerImageId"])
            elif 'dockerPull' in docker_req:
                img_id = str(docker_req["dockerPull"])
            else:
                raise WorkflowException(SourceLine(docker_req).makeError(
                    "Docker image must be specified as 'dockerImageId' or "
                    "'dockerPull' when using user space implementations of "
                    "Docker"))
        else:
            try:
                if docker_req and runtimeContext.use_container:
                    img_id = str(
                        self.get_from_requirements(
                            docker_req, True, runtimeContext.pull_image,
                            getdefault(runtimeContext.force_docker_pull, False),
                            getdefault(runtimeContext.tmp_outdir_prefix, DEFAULT_TMP_PREFIX)))
                if img_id is None:
                    if self.builder.find_default_container:
                        default_container = self.builder.find_default_container()
                        if default_container:
                            img_id = str(default_container)

                if docker_req and img_id is None and runtimeContext.use_container:
                    raise Exception("Docker image not available")

                if self.prov_obj and img_id and runtimeContext.process_run_id:
                    # TODO: Integrate with record_container_id
                    container_agent = self.prov_obj.document.agent(
                        uuid.uuid4().urn,
                        {"prov:type": PROV["SoftwareAgent"],
                         "cwlprov:image": img_id,
                         "prov:label": "Container execution of image %s" % img_id})
                    # FIXME: img_id is not a sha256 id, it might just be "debian:8"
                    #img_entity = document.entity("nih:sha-256;%s" % img_id,
                    #                  {"prov:label": "Container image %s" % img_id} )
                    # The image is the plan for this activity-agent association
                    #document.wasAssociatedWith(process_run_ID, container_agent, img_entity)
                    self.prov_obj.document.wasAssociatedWith(
                        runtimeContext.process_run_id, container_agent)
            except Exception as err:
                container = "Singularity" if runtimeContext.singularity else "Docker"
                _logger.debug("%s error", container, exc_info=True)
                if docker_is_req:
                    raise UnsupportedRequirement(
                        "%s is required to run this tool: %s" % (container, err))
                else:
                    raise WorkflowException(
                        "{0} is not available for this tool, try "
                        "--no-container to disable {0}, or install "
                        "a user space Docker replacement like uDocker with "
                        "--user-space-docker-cmd.: {1}".format(container, err))

        self._setup(runtimeContext)
        runtime = self.create_runtime(env, runtimeContext)
        runtime.append(img_id)
        self._execute(runtime, env, runtimeContext)


def _job_popen(
        commands,                  # type: List[Text]
        stdin_path,                # type: Optional[Text]
        stdout_path,               # type: Optional[Text]
        stderr_path,               # type: Optional[Text]
        env,                       # type: MutableMapping[AnyStr, AnyStr]
        cwd,                       # type: Text
        job_dir,                   # type: Text
        job_script_contents=None,  # type: Text
        timelimit=None,            # type: int
        name=None                  # type: Text
       ):  # type: (...) -> int

    if not job_script_contents and not FORCE_SHELLED_POPEN:

        stdin = subprocess.PIPE  # type: Union[IO[Any], int]
        if stdin_path is not None:
            stdin = open(stdin_path, "rb")

        stdout = sys.stderr  # type: IO[Any]
        if stdout_path is not None:
            stdout = open(stdout_path, "wb")

        stderr = sys.stderr  # type: IO[Any]
        if stderr_path is not None:
            stderr = open(stderr_path, "wb")

        sproc = subprocess.Popen(commands,
                                 shell=False,
                                 close_fds=not onWindows(),
                                 stdin=stdin,
                                 stdout=stdout,
                                 stderr=stderr,
                                 env=env,
                                 cwd=cwd)
        processes_to_kill.append(sproc)

        if sproc.stdin:
            sproc.stdin.close()

        tm = None
        if timelimit:
            def terminate():
                try:
                    _logger.warn(u"[job %s] exceeded time limit of %d seconds and will be terminated", name, timelimit)
                    sproc.terminate()
                except OSError:
                    pass
            tm = Timer(timelimit, terminate)
            tm.daemon = True
            tm.start()

        rcode = sproc.wait()

        if tm:
            tm.cancel()

        if isinstance(stdin, IOBase):
            stdin.close()

        if stdout is not sys.stderr:
            stdout.close()

        if stderr is not sys.stderr:
            stderr.close()

        return rcode
    else:
        if not job_script_contents:
            job_script_contents = SHELL_COMMAND_TEMPLATE

        env_copy = {}
        key = None  # type: Any
        for key in env:
            env_copy[key] = env[key]

        job_description = {
            u"commands": commands,
            u"cwd": cwd,
            u"env": env_copy,
            u"stdout_path": stdout_path,
            u"stderr_path": stderr_path,
            u"stdin_path": stdin_path}

        if PY2:
            with open(os.path.join(job_dir, "job.json"), mode="wb") as job_file:
                json_dump(job_description, job_file, ensure_ascii=False)
        else:
            with open(os.path.join(job_dir, "job.json"), mode="w",
                      encoding='utf-8') as job_file:
                json_dump(job_description, job_file, ensure_ascii=False)
        try:
            job_script = os.path.join(job_dir, "run_job.bash")
            with open(job_script, "wb") as _:
                _.write(job_script_contents.encode('utf-8'))
            job_run = os.path.join(job_dir, "run_job.py")
            with open(job_run, "wb") as _:
                _.write(PYTHON_RUN_SCRIPT.encode('utf-8'))
            sproc = subprocess.Popen(
                ["bash", job_script.encode("utf-8")],
                shell=False,
                cwd=job_dir,
                # The nested script will output the paths to the correct files if they need
                # to be captured. Else just write everything to stderr (same as above).
                stdout=sys.stderr,
                stderr=sys.stderr,
                stdin=subprocess.PIPE,
            )
            processes_to_kill.append(sproc)
            if sproc.stdin:
                sproc.stdin.close()

            rcode = sproc.wait()

            return rcode
        finally:
            shutil.rmtree(job_dir)
