import datetime
import functools
import itertools
import logging
import math
import os
import re
import shutil
import signal
import stat
import subprocess  # nosec
import sys
import tempfile
import threading
import time
import uuid
from abc import ABCMeta, abstractmethod
from threading import Timer
from typing import (
    IO,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Match,
    MutableMapping,
    MutableSequence,
    Optional,
    TextIO,
    Tuple,
    Union,
    cast,
)

import psutil
import shellescape
from prov.model import PROV
from schema_salad.sourceline import SourceLine
from schema_salad.utils import json_dump, json_dumps
from typing_extensions import TYPE_CHECKING

from . import env_to_stdout, run_job
from .builder import Builder
from .context import RuntimeContext
from .cuda import cuda_check
from .errors import UnsupportedRequirement, WorkflowException
from .loghandler import _logger
from .pathmapper import MapperEnt, PathMapper
from .process import stage_files
from .secrets import SecretStore
from .utils import (
    CWLObjectType,
    CWLOutputType,
    DirectoryType,
    HasReqsHints,
    OutputCallbackType,
    bytes2str_in_dicts,
    create_tmp_dir,
    ensure_non_writable,
    ensure_writable,
    processes_to_kill,
)

if TYPE_CHECKING:
    from .provenance_profile import ProvenanceProfile  # pylint: disable=unused-import
needs_shell_quoting_re = re.compile(r"""(^$|[\s|&;()<>\'"$@])""")

FORCE_SHELLED_POPEN = os.getenv("CWLTOOL_FORCE_SHELL_POPEN", "0") == "1"

SHELL_COMMAND_TEMPLATE = """#!/bin/bash
python3 "run_job.py" "job.json"
"""


def relink_initialworkdir(
    pathmapper: PathMapper,
    host_outdir: str,
    container_outdir: str,
    inplace_update: bool = False,
) -> None:
    for _, vol in pathmapper.items_exclude_children():
        if not vol.staged:
            continue

        if vol.type in ("File", "Directory") or (
            inplace_update and vol.type in ("WritableFile", "WritableDirectory")
        ):
            if not vol.target.startswith(container_outdir):
                # this is an input file written outside of the working
                # directory, so therefore ineligable for being an output file.
                # Thus, none of our business
                continue
            host_outdir_tgt = os.path.join(
                host_outdir, vol.target[len(container_outdir) + 1 :]
            )
            if os.path.islink(host_outdir_tgt) or os.path.isfile(host_outdir_tgt):
                try:
                    os.remove(host_outdir_tgt)
                except PermissionError:
                    pass
            elif os.path.isdir(host_outdir_tgt) and not vol.resolved.startswith("_:"):
                shutil.rmtree(host_outdir_tgt)
            if not vol.resolved.startswith("_:"):
                try:
                    os.symlink(vol.resolved, host_outdir_tgt)
                except FileExistsError:
                    pass


def neverquote(string: str, pos: int = 0, endpos: int = 0) -> Optional[Match[str]]:
    return None


CollectOutputsType = Union[Callable[[str, int], CWLObjectType], functools.partial]


class JobBase(HasReqsHints, metaclass=ABCMeta):
    def __init__(
        self,
        builder: Builder,
        joborder: CWLObjectType,
        make_path_mapper: Callable[..., PathMapper],
        requirements: List[CWLObjectType],
        hints: List[CWLObjectType],
        name: str,
    ) -> None:
        """Initialize the job object."""
        super().__init__()
        self.builder = builder
        self.joborder = joborder
        self.stdin = None  # type: Optional[str]
        self.stderr = None  # type: Optional[str]
        self.stdout = None  # type: Optional[str]
        self.successCodes = []  # type: Iterable[int]
        self.temporaryFailCodes = []  # type: Iterable[int]
        self.permanentFailCodes = []  # type: Iterable[int]
        self.requirements = requirements
        self.hints = hints
        self.name = name
        self.command_line = []  # type: List[str]
        self.pathmapper = PathMapper([], "", "")
        self.make_path_mapper = make_path_mapper
        self.generatemapper = None  # type: Optional[PathMapper]

        # set in CommandLineTool.job(i)
        self.collect_outputs = cast(CollectOutputsType, None)
        self.output_callback = None  # type: Optional[OutputCallbackType]
        self.outdir = ""
        self.tmpdir = ""

        self.environment = {}  # type: MutableMapping[str, str]
        self.generatefiles = {
            "class": "Directory",
            "listing": [],
            "basename": "",
        }  # type: DirectoryType
        self.stagedir = None  # type: Optional[str]
        self.inplace_update = False
        self.prov_obj = None  # type: Optional[ProvenanceProfile]
        self.parent_wf = None  # type: Optional[ProvenanceProfile]
        self.timelimit = None  # type: Optional[int]
        self.networkaccess = False  # type: bool
        self.mpi_procs = None  # type: Optional[int]

    def __repr__(self):  # type: () -> str
        """Represent this Job object."""
        return "CommandLineJob(%s)" % self.name

    @abstractmethod
    def run(
        self,
        runtimeContext: RuntimeContext,
        tmpdir_lock: Optional[threading.Lock] = None,
    ) -> None:
        pass

    def _setup(self, runtimeContext: RuntimeContext) -> None:

        cuda_req, _ = self.builder.get_requirement(
            "http://commonwl.org/cwltool#CUDARequirement"
        )
        if cuda_req:
            count = cuda_check(
                cuda_req, math.ceil(self.builder.resources["cudaDeviceCount"])
            )
            if count == 0:
                raise WorkflowException("Could not satisfy CUDARequirement")

        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)

        def is_streamable(file: str) -> bool:
            if not runtimeContext.streaming_allowed:
                return False
            for inp in self.joborder.values():
                if isinstance(inp, dict) and inp.get("location", None) == file:
                    return inp.get("streamable", False)
            return False

        for knownfile in self.pathmapper.files():
            p = self.pathmapper.mapper(knownfile)
            if p.type == "File" and not os.path.isfile(p[0]) and p.staged:
                if not (
                    is_streamable(knownfile) and stat.S_ISFIFO(os.stat(p[0]).st_mode)
                ):
                    raise WorkflowException(
                        "Input file %s (at %s) not found or is not a regular "
                        "file." % (knownfile, self.pathmapper.mapper(knownfile)[0])
                    )

        if "listing" in self.generatefiles:
            runtimeContext = runtimeContext.copy()
            runtimeContext.outdir = self.outdir
            self.generatemapper = self.make_path_mapper(
                self.generatefiles["listing"],
                self.builder.outdir,
                runtimeContext,
                False,
            )
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(
                    "[job %s] initial work dir %s",
                    self.name,
                    json_dumps(
                        {
                            p: self.generatemapper.mapper(p)
                            for p in self.generatemapper.files()
                        },
                        indent=4,
                    ),
                )
        self.base_path_logs = runtimeContext.set_log_dir(
            self.outdir, runtimeContext.log_dir, self.name
        )

    def _execute(
        self,
        runtime: List[str],
        env: MutableMapping[str, str],
        runtimeContext: RuntimeContext,
        monitor_function=None,  # type: Optional[Callable[[subprocess.Popen[str]], None]]
    ) -> None:
        """Execute the tool, either directly or via script.

        Note: we are now at the point where self.environment is
        ignored. The caller is responsible for correctly splitting that
        into the runtime and env arguments.

        `runtime` is the list of arguments to put at the start of the
        command (e.g. docker run).

        `env` is the environment to be set for running the resulting
        command line.
        """
        scr = self.get_requirement("ShellCommandRequirement")[0]

        shouldquote = needs_shell_quoting_re.search
        if scr is not None:
            shouldquote = neverquote

        # If mpi_procs (is not None and > 0) then prepend the
        # appropriate MPI job launch command and flags before the
        # execution.
        if self.mpi_procs:
            menv = runtimeContext.mpi_config
            mpi_runtime = [
                menv.runner,
                menv.nproc_flag,
                str(self.mpi_procs),
            ] + menv.extra_flags
            runtime = mpi_runtime + runtime
            menv.pass_through_env_vars(env)
            menv.set_env_vars(env)

        _logger.info(
            "[job %s] %s$ %s%s%s%s",
            self.name,
            self.outdir,
            " \\\n    ".join(
                [
                    shellescape.quote(str(arg)) if shouldquote(str(arg)) else str(arg)
                    for arg in (runtime + self.command_line)
                ]
            ),
            " < %s" % self.stdin if self.stdin else "",
            " > %s" % os.path.join(self.base_path_logs, self.stdout)
            if self.stdout
            else "",
            " 2> %s" % os.path.join(self.base_path_logs, self.stderr)
            if self.stderr
            else "",
        )
        if self.joborder is not None and runtimeContext.research_obj is not None:
            job_order = self.joborder
            if (
                runtimeContext.process_run_id is not None
                and runtimeContext.prov_obj is not None
                and isinstance(job_order, (list, dict))
            ):
                runtimeContext.prov_obj.used_artefacts(
                    job_order, runtimeContext.process_run_id, str(self.name)
                )
            else:
                _logger.warning(
                    "research_obj set but one of process_run_id "
                    "or prov_obj is missing from runtimeContext: "
                    "{}".format(runtimeContext)
                )
        outputs = {}  # type: CWLObjectType
        try:
            stdin_path = None
            if self.stdin is not None:
                rmap = self.pathmapper.reversemap(self.stdin)
                if rmap is None:
                    raise WorkflowException(f"{self.stdin} missing from pathmapper")
                else:
                    stdin_path = rmap[1]

            def stderr_stdout_log_path(
                base_path_logs: str, stderr_or_stdout: Optional[str]
            ) -> Optional[str]:
                if stderr_or_stdout is not None:
                    abserr = os.path.join(base_path_logs, stderr_or_stdout)
                    dnerr = os.path.dirname(abserr)
                    if dnerr and not os.path.exists(dnerr):
                        os.makedirs(dnerr)
                    return abserr
                return None

            stderr_path = stderr_stdout_log_path(self.base_path_logs, self.stderr)
            stdout_path = stderr_stdout_log_path(self.base_path_logs, self.stdout)
            commands = [str(x) for x in runtime + self.command_line]
            if runtimeContext.secret_store is not None:
                commands = cast(
                    List[str],
                    runtimeContext.secret_store.retrieve(cast(CWLOutputType, commands)),
                )
                env = cast(
                    MutableMapping[str, str],
                    runtimeContext.secret_store.retrieve(cast(CWLOutputType, env)),
                )

            job_script_contents = None  # type: Optional[str]
            builder: Optional[Builder] = getattr(self, "builder", None)
            if builder is not None:
                job_script_contents = builder.build_job_script(commands)
            rcode = _job_popen(
                commands,
                stdin_path=stdin_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                env=env,
                cwd=self.outdir,
                make_job_dir=lambda: runtimeContext.create_outdir(),
                job_script_contents=job_script_contents,
                timelimit=self.timelimit,
                name=self.name,
                monitor_function=monitor_function,
                default_stdout=runtimeContext.default_stdout,
                default_stderr=runtimeContext.default_stderr,
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

            if processStatus != "success":
                if rcode < 0:
                    _logger.warning(
                        "[job %s] was terminated by signal: %s",
                        self.name,
                        signal.Signals(-rcode).name,
                    )
                else:
                    _logger.warning("[job %s] exited with status: %d", self.name, rcode)

            if "listing" in self.generatefiles:
                if self.generatemapper:
                    relink_initialworkdir(
                        self.generatemapper,
                        self.outdir,
                        self.builder.outdir,
                        inplace_update=self.inplace_update,
                    )
                else:
                    raise ValueError(
                        "'listing' in self.generatefiles but no "
                        "generatemapper was setup."
                    )
            runtimeContext.log_dir_handler(
                self.outdir, self.base_path_logs, stdout_path, stderr_path
            )
            outputs = self.collect_outputs(self.outdir, rcode)
            outputs = bytes2str_in_dicts(outputs)  # type: ignore
        except OSError as e:
            if e.errno == 2:
                if runtime:
                    _logger.error("'%s' not found: %s", runtime[0], str(e))
                else:
                    _logger.error("'%s' not found: %s", self.command_line[0], str(e))
            else:
                _logger.exception("Exception while running job")
            processStatus = "permanentFail"
        except WorkflowException as err:
            _logger.error("[job %s] Job error:\n%s", self.name, str(err))
            processStatus = "permanentFail"
        except Exception:
            _logger.exception("Exception while running job")
            processStatus = "permanentFail"
        if (
            runtimeContext.research_obj is not None
            and self.prov_obj is not None
            and runtimeContext.process_run_id is not None
        ):
            # creating entities for the outputs produced by each step (in the provenance document)
            self.prov_obj.record_process_end(
                str(self.name),
                runtimeContext.process_run_id,
                outputs,
                datetime.datetime.now(),
            )
        if processStatus != "success":
            _logger.warning("[job %s] completed %s", self.name, processStatus)
        else:
            _logger.info("[job %s] completed %s", self.name, processStatus)

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "[job %s] outputs %s", self.name, json_dumps(outputs, indent=4)
            )

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
                                host_outdir, p.target[len(container_outdir) + 1 :]
                            )
                        os.remove(host_outdir_tgt)

        if runtimeContext.workflow_eval_lock is None:
            raise WorkflowException(
                "runtimeContext.workflow_eval_lock must not be None"
            )

        if self.output_callback:
            with runtimeContext.workflow_eval_lock:
                self.output_callback(outputs, processStatus)

        if self.stagedir is not None and os.path.exists(self.stagedir):
            _logger.debug(
                "[job %s] Removing input staging directory %s",
                self.name,
                self.stagedir,
            )
            shutil.rmtree(self.stagedir, True)

        if runtimeContext.rm_tmpdir:
            _logger.debug(
                "[job %s] Removing temporary directory %s", self.name, self.tmpdir
            )
            shutil.rmtree(self.tmpdir, True)

    @abstractmethod
    def _required_env(self) -> Dict[str, str]:
        """Variables required by the CWL spec (HOME, TMPDIR, etc).

        Note that with containers, the paths will (likely) be those from
        inside.
        """

    def _preserve_environment_on_containers_warning(
        self, varname: Optional[Iterable[str]] = None
    ) -> None:
        """When running in a container, issue a warning."""
        # By default, don't do anything; ContainerCommandLineJob below
        # will issue a warning.

    def prepare_environment(
        self, runtimeContext: RuntimeContext, envVarReq: Mapping[str, str]
    ) -> None:
        """Set up environment variables.

        Here we prepare the environment for the job, based on any
        preserved variables and `EnvVarRequirement`. Later, changes due
        to `MPIRequirement`, `Secrets`, or `SoftwareRequirement` are
        applied (in that order).
        """
        # Start empty
        env: Dict[str, str] = {}

        # Preserve any env vars
        if runtimeContext.preserve_entire_environment:
            self._preserve_environment_on_containers_warning()
            env.update(os.environ)
        elif runtimeContext.preserve_environment:
            self._preserve_environment_on_containers_warning(
                runtimeContext.preserve_environment
            )
            for key in runtimeContext.preserve_environment:
                try:
                    env[key] = os.environ[key]
                except KeyError:
                    _logger.warning(
                        f"Attempting to preserve environment variable '{key}' which is not present"
                    )

        # Set required env vars
        env.update(self._required_env())

        # Apply EnvVarRequirement
        env.update(envVarReq)

        # Set on ourselves
        self.environment = env

    def process_monitor(self, sproc):  # type: (subprocess.Popen[str]) -> None
        monitor = psutil.Process(sproc.pid)
        # Value must be list rather than integer to utilise pass-by-reference in python
        memory_usage = [None]  # type: MutableSequence[Optional[int]]

        def get_tree_mem_usage(memory_usage: MutableSequence[Optional[int]]) -> None:
            children = monitor.children()
            try:
                rss = monitor.memory_info().rss
                while len(children):
                    rss += sum(process.memory_info().rss for process in children)
                    children = list(
                        itertools.chain(*(process.children() for process in children))
                    )
                if memory_usage[0] is None or rss > memory_usage[0]:
                    memory_usage[0] = rss
            except psutil.NoSuchProcess:
                mem_tm.cancel()

        mem_tm = Timer(interval=1, function=get_tree_mem_usage, args=(memory_usage,))
        mem_tm.daemon = True
        mem_tm.start()
        sproc.wait()
        mem_tm.cancel()
        if memory_usage[0] is not None:
            _logger.info(
                "[job %s] Max memory used: %iMiB",
                self.name,
                round(memory_usage[0] / (2**20)),
            )
        else:
            _logger.debug(
                "Could not collect memory usage, job ended before monitoring began."
            )


class CommandLineJob(JobBase):
    def run(
        self,
        runtimeContext: RuntimeContext,
        tmpdir_lock: Optional[threading.Lock] = None,
    ) -> None:

        if tmpdir_lock:
            with tmpdir_lock:
                if not os.path.exists(self.tmpdir):
                    os.makedirs(self.tmpdir)
        else:
            if not os.path.exists(self.tmpdir):
                os.makedirs(self.tmpdir)

        self._setup(runtimeContext)

        stage_files(
            self.pathmapper,
            ignore_writable=True,
            symlink=True,
            secret_store=runtimeContext.secret_store,
        )
        if self.generatemapper is not None:
            stage_files(
                self.generatemapper,
                ignore_writable=self.inplace_update,
                symlink=True,
                secret_store=runtimeContext.secret_store,
            )
            relink_initialworkdir(
                self.generatemapper,
                self.outdir,
                self.builder.outdir,
                inplace_update=self.inplace_update,
            )

        monitor_function = functools.partial(self.process_monitor)

        self._execute([], self.environment, runtimeContext, monitor_function)

    def _required_env(self) -> Dict[str, str]:
        env = {}
        env["HOME"] = self.outdir
        env["TMPDIR"] = self.tmpdir
        env["PATH"] = os.environ["PATH"]
        if "SYSTEMROOT" in os.environ:
            env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        return env


CONTROL_CODE_RE = r"\x1b\[[0-9;]*[a-zA-Z]"


class ContainerCommandLineJob(JobBase, metaclass=ABCMeta):
    """Commandline job using containers."""

    CONTAINER_TMPDIR: str = "/tmp"  # nosec

    @abstractmethod
    def get_from_requirements(
        self,
        r: CWLObjectType,
        pull_image: bool,
        force_pull: bool,
        tmp_outdir_prefix: str,
    ) -> Optional[str]:
        pass

    @abstractmethod
    def create_runtime(
        self,
        env: MutableMapping[str, str],
        runtime_context: RuntimeContext,
    ) -> Tuple[List[str], Optional[str]]:
        """Return the list of commands to run the selected container engine."""

    @staticmethod
    @abstractmethod
    def append_volume(
        runtime: List[str], source: str, target: str, writable: bool = False
    ) -> None:
        """Add binding arguments to the runtime list."""

    @abstractmethod
    def add_file_or_directory_volume(
        self, runtime: List[str], volume: MapperEnt, host_outdir_tgt: Optional[str]
    ) -> None:
        """Append volume a file/dir mapping to the runtime option list."""

    @abstractmethod
    def add_writable_file_volume(
        self,
        runtime: List[str],
        volume: MapperEnt,
        host_outdir_tgt: Optional[str],
        tmpdir_prefix: str,
    ) -> None:
        """Append a writable file mapping to the runtime option list."""

    @abstractmethod
    def add_writable_directory_volume(
        self,
        runtime: List[str],
        volume: MapperEnt,
        host_outdir_tgt: Optional[str],
        tmpdir_prefix: str,
    ) -> None:
        """Append a writable directory mapping to the runtime option list."""

    def _preserve_environment_on_containers_warning(
        self, varnames: Optional[Iterable[str]] = None
    ) -> None:
        """When running in a container, issue a warning."""
        if varnames is None:
            flags = "--preserve-entire-environment"
        else:
            flags = "--preserve-environment={" + ", ".join(varnames) + "}"

        _logger.warning(
            f"You have specified `{flags}` while running a container which will override variables set in the container. This may break the container, be non-portable, and/or affect reproducibility."
        )

    def create_file_and_add_volume(
        self,
        runtime: List[str],
        volume: MapperEnt,
        host_outdir_tgt: Optional[str],
        secret_store: Optional[SecretStore],
        tmpdir_prefix: str,
    ) -> str:
        """Create the file and add a mapping."""
        if not host_outdir_tgt:
            new_file = os.path.join(
                create_tmp_dir(tmpdir_prefix),
                os.path.basename(volume.target),
            )
        writable = True if volume.type == "CreateWritableFile" else False
        contents = volume.resolved
        if secret_store:
            contents = cast(str, secret_store.retrieve(volume.resolved))
        dirname = os.path.dirname(host_outdir_tgt or new_file)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with open(host_outdir_tgt or new_file, "w") as file_literal:
            file_literal.write(contents)
        if not host_outdir_tgt:
            self.append_volume(runtime, new_file, volume.target, writable=writable)
        if writable:
            ensure_writable(host_outdir_tgt or new_file)
        else:
            ensure_non_writable(host_outdir_tgt or new_file)
        return host_outdir_tgt or new_file

    def add_volumes(
        self,
        pathmapper: PathMapper,
        runtime: List[str],
        tmpdir_prefix: str,
        secret_store: Optional[SecretStore] = None,
        any_path_okay: bool = False,
    ) -> None:
        """Append volume mappings to the runtime option list."""
        container_outdir = self.builder.outdir
        for key, vol in (itm for itm in pathmapper.items() if itm[1].staged):
            host_outdir_tgt = None  # type: Optional[str]
            if vol.target.startswith(container_outdir + "/"):
                host_outdir_tgt = os.path.join(
                    self.outdir, vol.target[len(container_outdir) + 1 :]
                )
            if not host_outdir_tgt and not any_path_okay:
                raise WorkflowException(
                    "No mandatory DockerRequirement, yet path is outside "
                    "the designated output directory, also know as "
                    "$(runtime.outdir): {}".format(vol)
                )
            if vol.type in ("File", "Directory"):
                self.add_file_or_directory_volume(runtime, vol, host_outdir_tgt)
            elif vol.type == "WritableFile":
                self.add_writable_file_volume(
                    runtime, vol, host_outdir_tgt, tmpdir_prefix
                )
            elif vol.type == "WritableDirectory":
                self.add_writable_directory_volume(
                    runtime, vol, host_outdir_tgt, tmpdir_prefix
                )
            elif vol.type in ["CreateFile", "CreateWritableFile"]:
                new_path = self.create_file_and_add_volume(
                    runtime, vol, host_outdir_tgt, secret_store, tmpdir_prefix
                )
                pathmapper.update(key, new_path, vol.target, vol.type, vol.staged)

    def run(
        self,
        runtimeContext: RuntimeContext,
        tmpdir_lock: Optional[threading.Lock] = None,
    ) -> None:
        debug = runtimeContext.debug
        if tmpdir_lock:
            with tmpdir_lock:
                if not os.path.exists(self.tmpdir):
                    os.makedirs(self.tmpdir)
        else:
            if not os.path.exists(self.tmpdir):
                os.makedirs(self.tmpdir)

        (docker_req, docker_is_req) = self.get_requirement("DockerRequirement")
        self.prov_obj = runtimeContext.prov_obj
        img_id = None
        user_space_docker_cmd = runtimeContext.user_space_docker_cmd
        if docker_req is not None and user_space_docker_cmd:
            # For user-space docker implementations, a local image name or ID
            # takes precedence over a network pull
            if "dockerImageId" in docker_req:
                img_id = str(docker_req["dockerImageId"])
            elif "dockerPull" in docker_req:
                img_id = str(docker_req["dockerPull"])
                cmd = [user_space_docker_cmd, "pull", img_id]
                _logger.info(str(cmd))
                try:
                    subprocess.check_call(cmd, stdout=sys.stderr)  # nosec
                except OSError:
                    raise SourceLine(
                        docker_req, None, WorkflowException, debug
                    ).makeError(
                        f"Either Docker container {img_id} is not available with "
                        f"user space docker implementation {user_space_docker_cmd} "
                        f" or {user_space_docker_cmd} is missing or broken."
                    )
            else:
                raise SourceLine(docker_req, None, WorkflowException, debug).makeError(
                    "Docker image must be specified as 'dockerImageId' or "
                    "'dockerPull' when using user space implementations of "
                    "Docker"
                )
        else:
            try:
                if docker_req is not None and runtimeContext.use_container:
                    img_id = str(
                        self.get_from_requirements(
                            docker_req,
                            runtimeContext.pull_image,
                            runtimeContext.force_docker_pull,
                            runtimeContext.tmp_outdir_prefix,
                        )
                    )
                if img_id is None:
                    if self.builder.find_default_container:
                        default_container = self.builder.find_default_container()
                        if default_container:
                            img_id = str(default_container)

                if (
                    docker_req is not None
                    and img_id is None
                    and runtimeContext.use_container
                ):
                    raise Exception("Docker image not available")

                if (
                    self.prov_obj is not None
                    and img_id is not None
                    and runtimeContext.process_run_id is not None
                ):
                    container_agent = self.prov_obj.document.agent(
                        uuid.uuid4().urn,
                        {
                            "prov:type": PROV["SoftwareAgent"],
                            "cwlprov:image": img_id,
                            "prov:label": "Container execution of image %s" % img_id,
                        },
                    )
                    # FIXME: img_id is not a sha256 id, it might just be "debian:8"
                    # img_entity = document.entity("nih:sha-256;%s" % img_id,
                    #                  {"prov:label": "Container image %s" % img_id} )
                    # The image is the plan for this activity-agent association
                    # document.wasAssociatedWith(process_run_ID, container_agent, img_entity)
                    self.prov_obj.document.wasAssociatedWith(
                        runtimeContext.process_run_id, container_agent
                    )
            except Exception as err:
                container = "Singularity" if runtimeContext.singularity else "Docker"
                _logger.debug("%s error", container, exc_info=True)
                if docker_is_req:
                    raise UnsupportedRequirement(
                        "{} is required to run this tool: {}".format(
                            container, str(err)
                        )
                    ) from err
                else:
                    raise WorkflowException(
                        "{0} is not available for this tool, try "
                        "--no-container to disable {0}, or install "
                        "a user space Docker replacement like uDocker with "
                        "--user-space-docker-cmd.: {1}".format(container, err)
                    )

        self._setup(runtimeContext)

        # Copy as don't want to modify our env
        env = dict(os.environ)
        (runtime, cidfile) = self.create_runtime(env, runtimeContext)

        runtime.append(str(img_id))
        monitor_function = None
        if cidfile:
            monitor_function = functools.partial(
                self.docker_monitor,
                cidfile,
                runtimeContext.tmpdir_prefix,
                not bool(runtimeContext.cidfile_dir),
            )
        elif runtimeContext.user_space_docker_cmd:
            monitor_function = functools.partial(self.process_monitor)
        self._execute(runtime, env, runtimeContext, monitor_function)

    def docker_monitor(
        self,
        cidfile: str,
        tmpdir_prefix: str,
        cleanup_cidfile: bool,
        process,  # type: subprocess.Popen[str]
    ) -> None:
        """Record memory usage of the running Docker container."""
        # Todo: consider switching to `docker create` / `docker start`
        # instead of `docker run` as `docker create` outputs the container ID
        # to stdout, but the container is frozen, thus allowing us to start the
        # monitoring process without dealing with the cidfile or too-fast
        # container execution
        cid = None  # type: Optional[str]
        while cid is None:
            time.sleep(1)
            if process.returncode is not None:
                if cleanup_cidfile:
                    try:
                        os.remove(cidfile)
                    except OSError as exc:
                        _logger.warning(
                            "Ignored error cleaning up Docker cidfile: %s", exc
                        )
                    return
            try:
                with open(cidfile) as cidhandle:
                    cid = cidhandle.readline().strip()
            except (OSError):
                cid = None
        max_mem = psutil.virtual_memory().total
        tmp_dir, tmp_prefix = os.path.split(tmpdir_prefix)
        stats_file = tempfile.NamedTemporaryFile(prefix=tmp_prefix, dir=tmp_dir)
        stats_file_name = stats_file.name
        try:
            with open(stats_file_name, mode="w") as stats_file_handle:
                stats_proc = subprocess.Popen(  # nosec
                    ["docker", "stats", "--no-trunc", "--format", "{{.MemPerc}}", cid],
                    stdout=stats_file_handle,
                    stderr=subprocess.DEVNULL,
                )
                process.wait()
                stats_proc.kill()
        except OSError as exc:
            _logger.warning("Ignored error with docker stats: %s", exc)
            return
        max_mem_percent = 0  # type: float
        mem_percent = 0  # type: float
        with open(stats_file_name) as stats:
            while True:
                line = stats.readline()
                if not line:
                    break
                try:
                    mem_percent = float(
                        re.sub(CONTROL_CODE_RE, "", line).replace("%", "")
                    )
                    if mem_percent > max_mem_percent:
                        max_mem_percent = mem_percent
                except ValueError:
                    break
        _logger.info(
            "[job %s] Max memory used: %iMiB",
            self.name,
            int((max_mem_percent / 100 * max_mem) / (2**20)),
        )
        if cleanup_cidfile:
            os.remove(cidfile)


def _job_popen(
    commands: List[str],
    stdin_path: Optional[str],
    stdout_path: Optional[str],
    stderr_path: Optional[str],
    env: Mapping[str, str],
    cwd: str,
    make_job_dir: Callable[[], str],
    job_script_contents: Optional[str] = None,
    timelimit: Optional[int] = None,
    name: Optional[str] = None,
    monitor_function=None,  # type: Optional[Callable[[subprocess.Popen[str]], None]]
    default_stdout=None,  # type: Optional[Union[IO[bytes], TextIO]]
    default_stderr=None,  # type: Optional[Union[IO[bytes], TextIO]]
) -> int:

    if job_script_contents is None and not FORCE_SHELLED_POPEN:

        stdin = subprocess.PIPE  # type: Union[IO[bytes], int]
        if stdin_path is not None:
            stdin = open(stdin_path, "rb")

        stdout = (
            default_stdout if default_stdout is not None else sys.stderr
        )  # type: Union[IO[bytes], TextIO]
        if stdout_path is not None:
            stdout = open(stdout_path, "wb")

        stderr = (
            default_stderr if default_stderr is not None else sys.stderr
        )  # type: Union[IO[bytes], TextIO]
        if stderr_path is not None:
            stderr = open(stderr_path, "wb")

        sproc = subprocess.Popen(
            commands,
            shell=False,  # nosec
            close_fds=True,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=env,
            cwd=cwd,
            universal_newlines=True,
        )
        processes_to_kill.append(sproc)

        if sproc.stdin is not None:
            sproc.stdin.close()

        tm = None
        if timelimit is not None and timelimit > 0:

            def terminate():  # type: () -> None
                try:
                    _logger.warning(
                        "[job %s] exceeded time limit of %d seconds and will be terminated",
                        name,
                        timelimit,
                    )
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

        if isinstance(stdin, IO) and hasattr(stdin, "close"):
            stdin.close()

        if stdout is not sys.stderr and hasattr(stdout, "close"):
            stdout.close()

        if stderr is not sys.stderr and hasattr(stderr, "close"):
            stderr.close()

        return rcode
    else:
        if job_script_contents is None:
            job_script_contents = SHELL_COMMAND_TEMPLATE

        job_description = {
            "commands": commands,
            "cwd": cwd,
            "env": env,
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
            "stdin_path": stdin_path,
        }

        job_dir = make_job_dir()
        try:
            with open(
                os.path.join(job_dir, "job.json"), mode="w", encoding="utf-8"
            ) as job_file:
                json_dump(job_description, job_file, ensure_ascii=False)
            job_script = os.path.join(job_dir, "run_job.bash")
            with open(job_script, "w") as _:
                _.write(job_script_contents)

            job_run = os.path.join(job_dir, "run_job.py")
            shutil.copyfile(run_job.__file__, job_run)

            env_getter = os.path.join(job_dir, "env_to_stdout.py")
            shutil.copyfile(env_to_stdout.__file__, env_getter)

            sproc = subprocess.Popen(  # nosec
                ["bash", job_script],
                shell=False,  # nosec
                cwd=job_dir,
                # The nested script will output the paths to the correct files if they need
                # to be captured. Else just write everything to stderr (same as above).
                stdout=sys.stderr,
                stderr=sys.stderr,
                stdin=subprocess.PIPE,
                universal_newlines=True,
            )
            processes_to_kill.append(sproc)
            if sproc.stdin is not None:
                sproc.stdin.close()

            rcode = sproc.wait()

            return rcode
        finally:
            shutil.rmtree(job_dir)
