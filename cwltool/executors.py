"""Single and multi-threaded executors."""
import datetime
import functools
import logging
import math
import os
import threading
from abc import ABCMeta, abstractmethod
from threading import Lock
from typing import (
    Dict,
    Iterable,
    List,
    MutableSequence,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

import psutil
from mypy_extensions import mypyc_attr
from schema_salad.exceptions import ValidationException
from schema_salad.sourceline import SourceLine

from .command_line_tool import CallbackJob, ExpressionJob
from .context import RuntimeContext, getdefault
from .errors import WorkflowException
from .job import JobBase
from .loghandler import _logger
from .mutation import MutationManager
from .process import Process, cleanIntermediate, relocateOutputs
from .provenance_profile import ProvenanceProfile
from .task_queue import TaskQueue
from .update import ORIGINAL_CWLVERSION
from .utils import CWLObjectType, JobsType
from .workflow import Workflow
from .workflow_job import WorkflowJob, WorkflowJobStep

TMPDIR_LOCK = Lock()


@mypyc_attr(allow_interpreted_subclasses=True)
class JobExecutor(metaclass=ABCMeta):
    """Abstract base job executor."""

    def __init__(self) -> None:
        """Initialize."""
        self.final_output: MutableSequence[Optional[CWLObjectType]] = []
        self.final_status: List[str] = []
        self.output_dirs: Set[str] = set()

    def __call__(
        self,
        process: Process,
        job_order_object: CWLObjectType,
        runtime_context: RuntimeContext,
        logger: logging.Logger = _logger,
    ) -> Tuple[Optional[CWLObjectType], str]:
        return self.execute(process, job_order_object, runtime_context, logger)

    def output_callback(self, out: Optional[CWLObjectType], process_status: str) -> None:
        """Collect the final status and outputs."""
        self.final_status.append(process_status)
        self.final_output.append(out)

    @abstractmethod
    def run_jobs(
        self,
        process: Process,
        job_order_object: CWLObjectType,
        logger: logging.Logger,
        runtime_context: RuntimeContext,
    ) -> None:
        """Execute the jobs for the given Process."""

    def execute(
        self,
        process: Process,
        job_order_object: CWLObjectType,
        runtime_context: RuntimeContext,
        logger: logging.Logger = _logger,
    ) -> Tuple[Union[Optional[CWLObjectType]], str]:
        """Execute the process."""
        if not runtime_context.basedir:
            raise WorkflowException("Must provide 'basedir' in runtimeContext")

        def check_for_abstract_op(tool: CWLObjectType) -> None:
            if tool["class"] == "Operation":
                raise SourceLine(tool, "class", WorkflowException, runtime_context.debug).makeError(
                    "Workflow has unrunnable abstract Operation"
                )

        process.visit(check_for_abstract_op)

        finaloutdir = None  # Type: Optional[str]
        original_outdir = runtime_context.outdir
        if isinstance(original_outdir, str):
            finaloutdir = os.path.abspath(original_outdir)
        runtime_context = runtime_context.copy()
        outdir = runtime_context.create_outdir()
        self.output_dirs.add(outdir)
        runtime_context.outdir = outdir
        runtime_context.mutation_manager = MutationManager()
        runtime_context.toplevel = True
        runtime_context.workflow_eval_lock = threading.Condition(threading.RLock())

        job_reqs: Optional[List[CWLObjectType]] = None
        if "https://w3id.org/cwl/cwl#requirements" in job_order_object:
            if process.metadata.get(ORIGINAL_CWLVERSION) == "v1.0":
                raise WorkflowException(
                    "`cwl:requirements` in the input object is not part of CWL "
                    "v1.0. You can adjust to use `cwltool:overrides` instead; or you "
                    "can set the cwlVersion to v1.1"
                )
            job_reqs = cast(
                List[CWLObjectType],
                job_order_object["https://w3id.org/cwl/cwl#requirements"],
            )
        elif "cwl:defaults" in process.metadata and "https://w3id.org/cwl/cwl#requirements" in cast(
            CWLObjectType, process.metadata["cwl:defaults"]
        ):
            if process.metadata.get(ORIGINAL_CWLVERSION) == "v1.0":
                raise WorkflowException(
                    "`cwl:requirements` in the input object is not part of CWL "
                    "v1.0. You can adjust to use `cwltool:overrides` instead; or you "
                    "can set the cwlVersion to v1.1"
                )
            job_reqs = cast(
                Optional[List[CWLObjectType]],
                cast(CWLObjectType, process.metadata["cwl:defaults"])[
                    "https://w3id.org/cwl/cwl#requirements"
                ],
            )
        if job_reqs is not None:
            for req in job_reqs:
                process.requirements.append(req)

        self.run_jobs(process, job_order_object, logger, runtime_context)

        if self.final_output and self.final_output[0] is not None and finaloutdir is not None:
            self.final_output[0] = relocateOutputs(
                self.final_output[0],
                finaloutdir,
                self.output_dirs,
                runtime_context.move_outputs,
                runtime_context.make_fs_access(""),
                getdefault(runtime_context.compute_checksum, True),
                path_mapper=runtime_context.path_mapper,
            )

        if runtime_context.rm_tmpdir:
            if not runtime_context.cachedir:
                output_dirs: Iterable[str] = self.output_dirs
            else:
                output_dirs = filter(
                    lambda x: not x.startswith(runtime_context.cachedir),  # type: ignore
                    self.output_dirs,
                )
            cleanIntermediate(output_dirs)

        if self.final_output and self.final_status:
            if (
                runtime_context.research_obj is not None
                and isinstance(process, (JobBase, Process, WorkflowJobStep, WorkflowJob))
                and process.parent_wf
            ):
                process_run_id: Optional[str] = None
                name = "primary"
                process.parent_wf.generate_output_prov(self.final_output[0], process_run_id, name)
                process.parent_wf.document.wasEndedBy(
                    process.parent_wf.workflow_run_uri,
                    None,
                    process.parent_wf.engine_uuid,
                    datetime.datetime.now(),
                )
                process.parent_wf.finalize_prov_profile(name=None)
            return (self.final_output[0], self.final_status[0])
        return (None, "permanentFail")


@mypyc_attr(allow_interpreted_subclasses=True)
class SingleJobExecutor(JobExecutor):
    """Default single-threaded CWL reference executor."""

    def run_jobs(
        self,
        process: Process,
        job_order_object: CWLObjectType,
        logger: logging.Logger,
        runtime_context: RuntimeContext,
    ) -> None:
        process_run_id: Optional[str] = None

        # define provenance profile for single commandline tool
        if not isinstance(process, Workflow) and runtime_context.research_obj is not None:
            process.provenance_object = ProvenanceProfile(
                runtime_context.research_obj,
                full_name=runtime_context.cwl_full_name,
                host_provenance=False,
                user_provenance=False,
                orcid=runtime_context.orcid,
                # single tool execution, so RO UUID = wf UUID = tool UUID
                run_uuid=runtime_context.research_obj.ro_uuid,
                fsaccess=runtime_context.make_fs_access(""),
            )
            process.parent_wf = process.provenance_object

        jobiter = process.job(job_order_object, self.output_callback, runtime_context)

        try:
            for job in jobiter:
                if job is not None:
                    if runtime_context.builder is not None and hasattr(job, "builder"):
                        job.builder = runtime_context.builder
                    if job.outdir is not None:
                        self.output_dirs.add(job.outdir)
                    if runtime_context.research_obj is not None:
                        if not isinstance(process, Workflow):
                            prov_obj = process.provenance_object
                        else:
                            prov_obj = job.prov_obj
                        if prov_obj:
                            runtime_context.prov_obj = prov_obj
                            prov_obj.fsaccess = runtime_context.make_fs_access("")
                            prov_obj.evaluate(
                                process,
                                job,
                                job_order_object,
                                runtime_context.research_obj,
                            )
                            process_run_id = prov_obj.record_process_start(process, job)
                            runtime_context = runtime_context.copy()
                        runtime_context.process_run_id = process_run_id
                    job.run(runtime_context)
                else:
                    logger.error("Workflow cannot make any more progress.")
                    break
        except (
            ValidationException,
            WorkflowException,
        ):  # pylint: disable=try-except-raise
            raise
        except Exception as err:
            logger.exception("Got workflow error")
            raise WorkflowException(str(err)) from err


class MultithreadedJobExecutor(JobExecutor):
    """
    Experimental multi-threaded CWL executor.

    Does simple resource accounting, will not start a job unless it
    has cores / ram available, but does not make any attempt to
    optimize usage.
    """

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self.exceptions: List[WorkflowException] = []
        self.pending_jobs: List[JobsType] = []
        self.pending_jobs_lock = threading.Lock()

        self.max_ram = int(psutil.virtual_memory().available / 2**20)
        self.max_cores = float(psutil.cpu_count())
        self.allocated_ram = float(0)
        self.allocated_cores = float(0)

    def select_resources(
        self, request: Dict[str, Union[int, float]], runtime_context: RuntimeContext
    ) -> Dict[str, Union[int, float]]:  # pylint: disable=unused-argument
        """Naïve check for available cpu cores and memory."""
        result: Dict[str, Union[int, float]] = {}
        maxrsc = {"cores": self.max_cores, "ram": self.max_ram}
        for rsc in ("cores", "ram"):
            rsc_min = request[rsc + "Min"]
            if rsc_min > maxrsc[rsc]:
                raise WorkflowException(
                    f"Requested at least {rsc_min} {rsc} but only " f"{maxrsc[rsc]} available"
                )
            rsc_max = request[rsc + "Max"]
            if rsc_max < maxrsc[rsc]:
                result[rsc] = math.ceil(rsc_max)
            else:
                result[rsc] = maxrsc[rsc]

        result["tmpdirSize"] = math.ceil(request["tmpdirMin"])
        result["outdirSize"] = math.ceil(request["outdirMin"])

        if "cudaDeviceCount" in request:
            result["cudaDeviceCount"] = request["cudaDeviceCount"]

        return result

    def _runner(
        self,
        job: Union[JobBase, WorkflowJob, CallbackJob, ExpressionJob],
        runtime_context: RuntimeContext,
        TMPDIR_LOCK: threading.Lock,
    ) -> None:
        """Job running thread."""
        try:
            _logger.debug(
                "job: {}, runtime_context: {}, TMPDIR_LOCK: {}".format(
                    job, runtime_context, TMPDIR_LOCK
                )
            )
            job.run(runtime_context, TMPDIR_LOCK)
        except WorkflowException as err:
            _logger.exception(f"Got workflow error: {err}")
            self.exceptions.append(err)
        except Exception as err:  # pylint: disable=broad-except
            _logger.exception(f"Got workflow error: {err}")
            self.exceptions.append(WorkflowException(str(err)))
        finally:
            if runtime_context.workflow_eval_lock:
                with runtime_context.workflow_eval_lock:
                    if isinstance(job, JobBase):
                        ram = job.builder.resources["ram"]
                        self.allocated_ram -= ram
                        cores = job.builder.resources["cores"]
                        self.allocated_cores -= cores
                    runtime_context.workflow_eval_lock.notify_all()

    def run_job(
        self,
        job: Optional[JobsType],
        runtime_context: RuntimeContext,
    ) -> None:
        """Execute a single Job in a separate thread."""
        if job is not None:
            with self.pending_jobs_lock:
                self.pending_jobs.append(job)

        with self.pending_jobs_lock:
            n = 0
            while (n + 1) <= len(self.pending_jobs):
                # Simple greedy resource allocation strategy.  Go
                # through pending jobs in the order they were
                # generated and add them to the queue only if there
                # are resources available.
                job = self.pending_jobs[n]
                if isinstance(job, JobBase):
                    ram = job.builder.resources["ram"]
                    cores = job.builder.resources["cores"]
                    if ram > self.max_ram or cores > self.max_cores:
                        _logger.error(
                            'Job "%s" cannot be run, requests more resources (%s) '
                            "than available on this host (max ram %d, max cores %d",
                            job.name,
                            job.builder.resources,
                            self.allocated_ram,
                            self.allocated_cores,
                            self.max_ram,
                            self.max_cores,
                        )
                        self.pending_jobs.remove(job)
                        return

                    if (
                        self.allocated_ram + ram > self.max_ram
                        or self.allocated_cores + cores > self.max_cores
                    ):
                        _logger.debug(
                            'Job "%s" cannot run yet, resources (%s) are not '
                            "available (already allocated ram is %d, allocated cores is %d, "
                            "max ram %d, max cores %d",
                            job.name,
                            job.builder.resources,
                            self.allocated_ram,
                            self.allocated_cores,
                            self.max_ram,
                            self.max_cores,
                        )
                        n += 1
                        continue

                if isinstance(job, JobBase):
                    ram = job.builder.resources["ram"]
                    self.allocated_ram += ram
                    cores = job.builder.resources["cores"]
                    self.allocated_cores += cores
                self.taskqueue.add(
                    functools.partial(self._runner, job, runtime_context, TMPDIR_LOCK),
                    runtime_context.workflow_eval_lock,
                )
                self.pending_jobs.remove(job)

    def wait_for_next_completion(self, runtime_context: RuntimeContext) -> None:
        """Wait for jobs to finish."""
        if runtime_context.workflow_eval_lock is not None:
            runtime_context.workflow_eval_lock.wait(timeout=3)
        if self.exceptions:
            raise self.exceptions[0]

    def run_jobs(
        self,
        process: Process,
        job_order_object: CWLObjectType,
        logger: logging.Logger,
        runtime_context: RuntimeContext,
    ) -> None:
        self.taskqueue: TaskQueue = TaskQueue(threading.Lock(), psutil.cpu_count())
        try:
            jobiter = process.job(job_order_object, self.output_callback, runtime_context)

            if runtime_context.workflow_eval_lock is None:
                raise WorkflowException("runtimeContext.workflow_eval_lock must not be None")

            runtime_context.workflow_eval_lock.acquire()
            for job in jobiter:
                if job is not None:
                    if isinstance(job, JobBase):
                        job.builder = runtime_context.builder or job.builder
                        if job.outdir is not None:
                            self.output_dirs.add(job.outdir)

                self.run_job(job, runtime_context)

                if job is None:
                    if self.taskqueue.in_flight > 0:
                        self.wait_for_next_completion(runtime_context)
                    else:
                        logger.error("Workflow cannot make any more progress.")
                        break

            self.run_job(None, runtime_context)
            while self.taskqueue.in_flight > 0:
                self.wait_for_next_completion(runtime_context)
                self.run_job(None, runtime_context)

            runtime_context.workflow_eval_lock.release()
        finally:
            self.taskqueue.drain()
            self.taskqueue.join()


class NoopJobExecutor(JobExecutor):
    """Do nothing executor, for testing purposes only."""

    def run_jobs(
        self,
        process: Process,
        job_order_object: CWLObjectType,
        logger: logging.Logger,
        runtime_context: RuntimeContext,
    ) -> None:
        pass

    def execute(
        self,
        process: Process,
        job_order_object: CWLObjectType,
        runtime_context: RuntimeContext,
        logger: Optional[logging.Logger] = None,
    ) -> Tuple[Optional[CWLObjectType], str]:
        return {}, "success"
