from __future__ import absolute_import

import datetime
import functools
import itertools
import logging
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import uuid
from abc import ABCMeta, abstractmethod
from io import IOBase, open  # pylint: disable=redefined-builtin
from threading import Timer
from typing import (IO, Any, AnyStr, Callable, Dict, Iterable, List, Tuple,
                    MutableMapping, MutableSequence, Optional, Union, cast)

import psutil
import shellescape
from prov.model import PROV
from schema_salad.sourceline import SourceLine
from six import PY2, with_metaclass
from typing_extensions import (TYPE_CHECKING,  # pylint: disable=unused-import
                               Text)

from .builder import Builder, HasReqsHints  # pylint: disable=unused-import
from .context import RuntimeContext  # pylint: disable=unused-import
from .context import getdefault
from .errors import WorkflowException
from .loghandler import _logger
from .pathmapper import (MapperEnt, PathMapper,  # pylint: disable=unused-import
                         ensure_writable, ensure_non_writable)
from .process import UnsupportedRequirement, stage_files
from .secrets import SecretStore  # pylint: disable=unused-import
from .utils import (DEFAULT_TMP_PREFIX, Directory, bytes2str_in_dicts,
                    copytree_with_merge, json_dump, json_dumps, onWindows,
                    processes_to_kill, subprocess)

if TYPE_CHECKING:
    from .provenance import ProvenanceProfile  # pylint: disable=unused-import
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


def relink_initialworkdir(pathmapper,           # type: PathMapper
                          host_outdir,          # type: Text
                          container_outdir,     # type: Text
                          inplace_update=False  # type: bool
                          ):  # type: (...) -> None
    for _, vol in pathmapper.items():
        if not vol.staged:
            continue

        if (vol.type in ("File", "Directory") or (
                inplace_update and vol.type in
                ("WritableFile", "WritableDirectory"))):
            if not vol.target.startswith(container_outdir):
                # this is an input file written outside of the working
                # directory, so therefor ineligable for being an output file.
                # Thus, none of our business
                continue
            host_outdir_tgt = os.path.join(
                host_outdir, vol.target[len(container_outdir) + 1:])
            if os.path.islink(host_outdir_tgt) \
                    or os.path.isfile(host_outdir_tgt):
                os.remove(host_outdir_tgt)
            elif os.path.isdir(host_outdir_tgt) \
                    and not vol.resolved.startswith("_:"):
                shutil.rmtree(host_outdir_tgt)
            if onWindows():
                # If this becomes a big issue for someone then we could
                # refactor the code to process output from a running container
                # and avoid all the extra IO below
                if vol.type in ("File", "WritableFile"):
                    shutil.copy(vol.resolved, host_outdir_tgt)
                elif vol.type in ("Directory", "WritableDirectory"):
                    copytree_with_merge(vol.resolved, host_outdir_tgt)
            elif not vol.resolved.startswith("_:"):
                os.symlink(vol.resolved, host_outdir_tgt)


class JobBase(with_metaclass(ABCMeta, HasReqsHints)):
    def __init__(self,
                 builder,           # type: Builder
                 joborder,          # type: Dict[Text, Union[Dict[Text, Any], List, Text, None]]
                 make_path_mapper,  # type: Callable[..., PathMapper]
                 requirements,      # type: List[Dict[Text, Text]]
                 hints,             # type: List[Dict[Text, Text]]
                 name,              # type: Text
                 ):  # type: (...) -> None
        self.builder = builder
        self.joborder = joborder
        self.stdin = None  # type: Optional[Text]
        self.stderr = None  # type: Optional[Text]
        self.stdout = None  # type: Optional[Text]
        self.successCodes = []  # type: Iterable[int]
        self.temporaryFailCodes = []  # type: Iterable[int]
        self.permanentFailCodes = []  # type: Iterable[int]
        self.requirements = requirements
        self.hints = hints
        self.name = name
        self.command_line = []  # type: List[Text]
        self.pathmapper = PathMapper([], u"", u"")
        self.make_path_mapper = make_path_mapper
        self.generatemapper = None  # type: Optional[PathMapper]

        # set in CommandLineTool.job(i)
        self.collect_outputs = cast(Callable[[Any], Any],
                                    None)  # type: Union[Callable[[Any], Any], functools.partial[Any]]
        self.output_callback = cast(Callable[[Any, Any], Any], None)
        self.outdir = u""
        self.tmpdir = u""

        self.environment = {}  # type: MutableMapping[Text, Text]
        self.generatefiles = {"class": "Directory", "listing": [], "basename": ""}  # type: Directory
        self.stagedir = None  # type: Optional[Text]
        self.inplace_update = False
        self.prov_obj = None  # type: Optional[ProvenanceProfile]
        self.parent_wf = None  # type: Optional[ProvenanceProfile]
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

        if 'listing' in self.generatefiles:
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
                 runtimeContext,         # type: RuntimeContext
                 monitor_function=None,  # type: Optional[Callable]
                 ):                      # type: (...) -> None

        scr, _ = self.get_requirement("ShellCommandRequirement")

        shouldquote = needs_shell_quoting_re.search  # type: Callable[[Any], Any]
        if scr is not None:
            shouldquote = lambda x: False

        _logger.info(u"[job %s] %s$ %s%s%s%s",
                     self.name,
                     self.outdir,
                     " \\\n    ".join([shellescape.quote(Text(arg)) if shouldquote(Text(arg)) else Text(arg) for arg in
                                       (runtime + self.command_line)]),
                     u' < %s' % self.stdin if self.stdin else '',
                     u' > %s' % os.path.join(self.outdir, self.stdout) if self.stdout else '',
                     u' 2> %s' % os.path.join(self.outdir, self.stderr) if self.stderr else '')
        if self.joborder is not None and runtimeContext.research_obj is not None:
            job_order = self.joborder
            assert runtimeContext.process_run_id is not None
            assert runtimeContext.prov_obj is not None
            runtimeContext.prov_obj.used_artefacts(
                job_order, runtimeContext.process_run_id, str(self.name))
        outputs = {}  # type: Dict[Text,Text]
        try:
            stdin_path = None
            if self.stdin is not None:
                rmap = self.pathmapper.reversemap(self.stdin)
                if rmap is None:
                    raise WorkflowException(
                        "{} missing from pathmapper".format(self.stdin))
                else:
                    stdin_path = rmap[1]

            stderr_path = None
            if self.stderr is not None:
                abserr = os.path.join(self.outdir, self.stderr)
                dnerr = os.path.dirname(abserr)
                if dnerr and not os.path.exists(dnerr):
                    os.makedirs(dnerr)
                stderr_path = abserr

            stdout_path = None
            if self.stdout is not None:
                absout = os.path.join(self.outdir, self.stdout)
                dnout = os.path.dirname(absout)
                if dnout and not os.path.exists(dnout):
                    os.makedirs(dnout)
                stdout_path = absout

            commands = [Text(x) for x in runtime + self.command_line]
            if runtimeContext.secret_store is not None:
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
                name=self.name,
                monitor_function=monitor_function
            )

            if rcode in self.successCodes:
                processStatus = "success"
            elif rcode in self.temporaryFailCodes:
                processStatus = "temporaryFail"
            elif rcode in self.permanentFailCodes:
                processStatus = "permanentFail"
            elif rcode == 0:
                processStatus = "success"
            else:
                processStatus = "permanentFail"

            if 'listing' in self.generatefiles:
                assert self.generatemapper is not None
                relink_initialworkdir(
                    self.generatemapper, self.outdir, self.builder.outdir,
                    inplace_update=self.inplace_update)

            outputs = self.collect_outputs(self.outdir)
            outputs = bytes2str_in_dicts(outputs)  # type: ignore
        except OSError as e:
            if e.errno == 2:
                if runtime:
                    _logger.error(u"'%s' not found: %s", runtime[0], e)
                else:
                    _logger.error(u"'%s' not found: %s", self.command_line[0], e)
            else:
                _logger.exception(u"Exception while running job")
            processStatus = "permanentFail"
        except WorkflowException as err:
            _logger.error(u"[job %s] Job error:\n%s", self.name, err)
            processStatus = "permanentFail"
        except Exception as e:
            _logger.exception(u"Exception while running job")
            processStatus = "permanentFail"
        if runtimeContext.research_obj is not None \
                and self.prov_obj is not None \
                and runtimeContext.process_run_id is not None:
            # creating entities for the outputs produced by each step (in the provenance document)
            self.prov_obj.record_process_end(str(self.name), runtimeContext.process_run_id,
                                             outputs, datetime.datetime.now())
        if processStatus != "success":
            _logger.warning(u"[job %s] completed %s", self.name, processStatus)
        else:
            _logger.info(u"[job %s] completed %s", self.name, processStatus)

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(u"[job %s] %s", self.name,
                          json_dumps(outputs, indent=4))

        if self.generatemapper is not None and runtimeContext.secret_store is not None:
            # Delete any runtime-generated files containing secrets.
            for _, p in self.generatemapper.items():
                if p.type == "CreateFile":
                    if runtimeContext.secret_store.has_secret(p.resolved):
                        host_outdir = self.outdir
                        container_outdir = self.builder.outdir
                        host_outdir_tgt = p.target
                        if p.target.startswith(container_outdir + "/"):
                            host_outdir_tgt = os.path.join(
                                host_outdir, p.target[len(container_outdir) + 1:])
                        os.remove(host_outdir_tgt)

        if runtimeContext.workflow_eval_lock is None:
            raise WorkflowException("runtimeContext.workflow_eval_lock must not be None")

        with runtimeContext.workflow_eval_lock:
            self.output_callback(outputs, processStatus)

        if self.stagedir is not None and os.path.exists(self.stagedir):
            _logger.debug(u"[job %s] Removing input staging directory %s", self.name, self.stagedir)
            shutil.rmtree(self.stagedir, True)

        if runtimeContext.rm_tmpdir:
            _logger.debug(u"[job %s] Removing temporary directory %s", self.name, self.tmpdir)
            shutil.rmtree(self.tmpdir, True)

    def process_monitor(self, sproc):
        monitor = psutil.Process(sproc.pid)
        memory_usage = [None]  # Value must be list rather than integer to utilise pass-by-reference in python

        def get_tree_mem_usage(memory_usage):
            children = monitor.children()
            rss = monitor.memory_info().rss
            while len(children):
                rss += sum([process.memory_info().rss for process in children])
                children = list(itertools.chain(*[process.children() for process in children]))
            if memory_usage[0] is None or rss > memory_usage[0]:
                memory_usage[0] = rss

        mem_tm = Timer(interval=1, function=get_tree_mem_usage, args=(memory_usage,))
        mem_tm.daemon = True
        mem_tm.start()
        sproc.wait()
        mem_tm.cancel()
        if memory_usage[0] is not None:
            _logger.info(u"[job %s] Max memory used: %iMiB", self.name,
                         round(memory_usage[0] / (2 ** 20)))
        else:
            _logger.info(u"Could not collect memory usage, job ended before monitoring began.")


class CommandLineJob(JobBase):
    def run(self,
            runtimeContext  # type: RuntimeContext
            ):  # type: (...) -> None

        if not os.path.exists(self.tmpdir):
            os.makedirs(self.tmpdir)
        self._setup(runtimeContext)

        env = self.environment
        vars_to_preserve = runtimeContext.preserve_environment
        if runtimeContext.preserve_entire_environment is not None:
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
            env["SYSTEMROOT"] = str(os.environ["SYSTEMROOT"]) if onWindows() \
                else os.environ["SYSTEMROOT"]

        stage_files(self.pathmapper, ignore_writable=True, symlink=True,
                    secret_store=runtimeContext.secret_store)
        if self.generatemapper is not None:
            stage_files(self.generatemapper, ignore_writable=self.inplace_update,
                        symlink=True, secret_store=runtimeContext.secret_store)
            relink_initialworkdir(
                self.generatemapper, self.outdir, self.builder.outdir,
                inplace_update=self.inplace_update)

        monitor_function = functools.partial(self.process_monitor)

        self._execute([], env, runtimeContext, monitor_function)


CONTROL_CODE_RE = r'\x1b\[[0-9;]*[a-zA-Z]'


class ContainerCommandLineJob(with_metaclass(ABCMeta, JobBase)):
    '''
    Commandline job using containers
    '''

    @abstractmethod
    def get_from_requirements(self,
                              r,                                    # type: Dict[Text, Text]
                              pull_image,                           # type: bool
                              force_pull=False,                     # type: bool
                              tmp_outdir_prefix=DEFAULT_TMP_PREFIX  # type: Text
                              ):  # type: (...) -> Optional[Text]
        pass

    @abstractmethod
    def create_runtime(self,
                       env,             # type: MutableMapping[Text, Text]
                       runtime_context  # type: RuntimeContext
                       ):  # type: (...) -> Tuple[List[Text], Optional[Text]]
        """ Return the list of commands to run the selected container engine."""
        pass

    @staticmethod
    @abstractmethod
    def append_volume(runtime, source, target, writable=False):
        # type: (List[Text], Text, Text, bool) -> None
        """Add binding arguments to the runtime list."""
        pass

    @abstractmethod
    def add_file_or_directory_volume(self,
                                     runtime,         # type: List[Text]
                                     volume,          # type: MapperEnt
                                     host_outdir_tgt  # type: Optional[Text]
                                     ):  # type: (...) -> None
        """Append volume a file/dir mapping to the runtime option list."""
        pass

    @abstractmethod
    def add_writable_file_volume(self,
                                 runtime,          # type: List[Text]
                                 volume,           # type: MapperEnt
                                 host_outdir_tgt,  # type: Optional[Text]
                                 tmpdir_prefix     # type: Text
                                 ):  # type: (...) -> None
        """Append a writable file mapping to the runtime option list."""
        pass

    @abstractmethod
    def add_writable_directory_volume(self,
                                      runtime,          # type: List[Text]
                                      volume,           # type: MapperEnt
                                      host_outdir_tgt,  # type: Optional[Text]
                                      tmpdir_prefix     # type: Text
                                      ):  # type: (...) -> None
        """Append a writable directory mapping to the runtime option list."""
        pass

    def create_file_and_add_volume(self,
                                   runtime,          # type: List[Text]
                                   volume,           # type: MapperEnt
                                   host_outdir_tgt,  # type: Optional[Text]
                                   secret_store,     # type: Optional[SecretStore]
                                   tmpdir_prefix     # type: Text
                                   ):  # type: (...) -> Text
        """Create the file and add a mapping."""
        if not host_outdir_tgt:
            new_file = os.path.join(
                tempfile.mkdtemp(dir=tmpdir_prefix),
                os.path.basename(volume.resolved))
        writable = True if volume.type == "CreateWritableFile" else False
        if secret_store:
            contents = secret_store.retrieve(volume.resolved)
        else:
            contents = volume.resolved
        dirname = os.path.dirname(host_outdir_tgt or new_file)
        if not os.path.exists(dirname):
            os.makedirs(dirname, 0o0755)
        with open(host_outdir_tgt or new_file, "wb") as file_literal:
            file_literal.write(contents.encode("utf-8"))
        if not host_outdir_tgt:
            self.append_volume(runtime, new_file, volume.target,
                               writable=writable)
        if writable:
            ensure_writable(host_outdir_tgt or new_file)
        else:
            ensure_non_writable(host_outdir_tgt or new_file)
        return host_outdir_tgt or new_file

    def add_volumes(self,
                    pathmapper,          # type: PathMapper
                    runtime,             # type: List[Text]
                    tmpdir_prefix,       # type: Text
                    secret_store=None,   # type: Optional[SecretStore]
                    any_path_okay=False  # type: bool
                    ):  # type: (...) -> None
        """Append volume mappings to the runtime option list."""

        container_outdir = self.builder.outdir
        for key, vol in (itm for itm in pathmapper.items() if itm[1].staged):
            host_outdir_tgt = None  # type: Optional[Text]
            if vol.target.startswith(container_outdir + "/"):
                host_outdir_tgt = os.path.join(
                    self.outdir, vol.target[len(container_outdir) + 1:])
            if not host_outdir_tgt and not any_path_okay:
                raise WorkflowException(
                    "No mandatory DockerRequirement, yet path is outside "
                    "the designated output directory, also know as "
                    "$(runtime.outdir): {}".format(vol))
            if vol.type in ("File", "Directory"):
                self.add_file_or_directory_volume(
                    runtime, vol, host_outdir_tgt)
            elif vol.type == "WritableFile":
                self.add_writable_file_volume(
                    runtime, vol, host_outdir_tgt, tmpdir_prefix)
            elif vol.type == "WritableDirectory":
                self.add_writable_directory_volume(
                    runtime, vol, host_outdir_tgt, tmpdir_prefix)
            elif vol.type in ["CreateFile", "CreateWritableFile"]:
                new_path = self.create_file_and_add_volume(
                    runtime, vol, host_outdir_tgt, secret_store, tmpdir_prefix)
                pathmapper.update(
                    key, new_path, vol.target, vol.type, vol.staged)

    def run(self, runtimeContext):  # type: (RuntimeContext) -> None
        if not os.path.exists(self.tmpdir):
            os.makedirs(self.tmpdir)
        (docker_req, docker_is_req) = self.get_requirement("DockerRequirement")
        self.prov_obj = runtimeContext.prov_obj
        img_id = None
        env = cast(MutableMapping[Text, Text], os.environ)
        user_space_docker_cmd = runtimeContext.user_space_docker_cmd
        if docker_req is not None and user_space_docker_cmd:
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
                if docker_req is not None and runtimeContext.use_container:
                    img_id = str(
                        self.get_from_requirements(
                            docker_req, runtimeContext.pull_image,
                            getdefault(runtimeContext.force_docker_pull, False),
                            getdefault(runtimeContext.tmp_outdir_prefix, DEFAULT_TMP_PREFIX)))
                if img_id is None:
                    if self.builder.find_default_container:
                        default_container = self.builder.find_default_container()
                        if default_container:
                            img_id = str(default_container)

                if docker_req is not None and img_id is None and runtimeContext.use_container:
                    raise Exception("Docker image not available")

                if self.prov_obj is not None and img_id is not None \
                        and runtimeContext.process_run_id is not None:
                    container_agent = self.prov_obj.document.agent(
                        uuid.uuid4().urn,
                        {"prov:type": PROV["SoftwareAgent"],
                         "cwlprov:image": img_id,
                         "prov:label": "Container execution of image %s" % img_id})
                    # FIXME: img_id is not a sha256 id, it might just be "debian:8"
                    # img_entity = document.entity("nih:sha-256;%s" % img_id,
                    #                  {"prov:label": "Container image %s" % img_id} )
                    # The image is the plan for this activity-agent association
                    # document.wasAssociatedWith(process_run_ID, container_agent, img_entity)
                    self.prov_obj.document.wasAssociatedWith(
                        runtimeContext.process_run_id, container_agent)
            except Exception as err:
                container = "Singularity" if runtimeContext.singularity else "Docker"
                _logger.debug(u"%s error", container, exc_info=True)
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
        (runtime, cidfile) = self.create_runtime(env, runtimeContext)
        runtime.append(Text(img_id))
        monitor_function = None
        if cidfile:
            monitor_function = functools.partial(
                self.docker_monitor, cidfile, runtimeContext.tmpdir_prefix,
                not bool(runtimeContext.cidfile_dir))
        elif runtimeContext.user_space_docker_cmd:
            monitor_function = functools.partial(self.process_monitor)
        self._execute(runtime, env, runtimeContext, monitor_function)

    @staticmethod
    def docker_get_memory(cid):  # type: (Text) -> int
        memory = None
        try:
            memory = subprocess.check_output(
                ['docker', 'inspect', '--type', 'container', '--format',
                 '{{.HostConfig.Memory}}', cid], stderr=subprocess.DEVNULL)  # type: ignore
        except subprocess.CalledProcessError:
            pass
        if memory:
            value = int(memory)
            if value != 0:
                return value
        return psutil.virtual_memory().total

    def docker_monitor(self, cidfile, tmpdir_prefix, cleanup_cidfile, process):
        # type: (Text, Text, bool, subprocess.Popen) -> None
        """Record memory usage of the running Docker container."""
        # Todo: consider switching to `docker create` / `docker start`
        # instead of `docker run` as `docker create` outputs the container ID
        # to stdout, but the container is frozen, thus allowing us to start the
        # monitoring process without dealing with the cidfile or too-fast
        # container execution
        cid = None
        while cid is None:
            time.sleep(1)
            if process.returncode is not None:
                if cleanup_cidfile:
                    os.remove(cidfile)
                return
            try:
                with open(cidfile) as cidhandle:
                    cid = cidhandle.readline().strip()
            except OSError:
                cid = None
        max_mem = self.docker_get_memory(cid)
        stats_file = tempfile.NamedTemporaryFile(dir=tmpdir_prefix)
        with open(stats_file.name, mode="w") as stats_file_handle:
            stats_proc = subprocess.Popen(
                ['docker', 'stats', '--no-trunc', '--format', '{{.MemPerc}}',
                 cid], stdout=stats_file_handle, stderr=subprocess.DEVNULL)
            process.wait()
            stats_proc.kill()
        max_mem_percent = 0
        with open(stats_file.name, mode="r") as stats:
            for line in stats:
                try:
                    mem_percent = float(re.sub(
                        CONTROL_CODE_RE, '', line).replace('%', ''))
                    if mem_percent > max_mem_percent:
                        max_mem_percent = mem_percent
                except ValueError:
                    break
        _logger.info(u"[job %s] Max memory used: %iMiB", self.name,
                     int((max_mem_percent * max_mem) / (2 ** 20)))
        if cleanup_cidfile:
            os.remove(cidfile)


def _job_popen(commands,                  # type: List[Text]
               stdin_path,                # type: Optional[Text]
               stdout_path,               # type: Optional[Text]
               stderr_path,               # type: Optional[Text]
               env,                       # type: MutableMapping[AnyStr, AnyStr]
               cwd,                       # type: Text
               job_dir,                   # type: Text
               job_script_contents=None,  # type: Text
               timelimit=None,            # type: int
               name=None,                 # type: Text
               monitor_function=None      # type: Optional[Callable]
               ):  # type: (...) -> int

    if job_script_contents is None and not FORCE_SHELLED_POPEN:

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

        if sproc.stdin is not None:
            sproc.stdin.close()

        tm = None
        if timelimit is not None:
            def terminate():
                try:
                    _logger.warning(
                        u"[job %s] exceeded time limit of %d seconds and will"
                        "be terminated", name, timelimit)
                    sproc.terminate()
                except OSError:
                    pass

            tm = Timer(timelimit, terminate)
            tm.daemon = True
            tm.start()
        if monitor_function:
            monitor_function(sproc)
        rcode = sproc.wait()

        if tm is not None:
            tm.cancel()

        if isinstance(stdin, IOBase):
            stdin.close()

        if stdout is not sys.stderr:
            stdout.close()

        if stderr is not sys.stderr:
            stderr.close()

        return rcode
    else:
        if job_script_contents is None:
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
            if sproc.stdin is not None:
                sproc.stdin.close()

            rcode = sproc.wait()

            return rcode
        finally:
            shutil.rmtree(job_dir)
