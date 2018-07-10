import os
import tempfile
import threading
from abc import ABCMeta, abstractmethod
import datetime
from typing import (Any, Dict, List, Optional,  # pylint: disable=unused-import
                    Set, Text, Tuple)

from schema_salad.validate import ValidationException
import six
from six import string_types

import psutil

from .builder import Builder  # pylint: disable=unused-import
from .errors import WorkflowException
from .loghandler import _logger
from .job import JobBase  # pylint: disable=unused-import
from .mutation import MutationManager
from .provenance import CreateProvProfile
from .process import (Process,  # pylint: disable=unused-import
                      cleanIntermediate, relocateOutputs)
from .utils import DEFAULT_TMP_PREFIX
from .context import RuntimeContext, getdefault  # pylint: disable=unused-import
from .workflow import Workflow, WorkflowJob, WorkflowJobStep

class JobExecutor(six.with_metaclass(ABCMeta, object)):
    """ Abstract base job executor. """

    def __init__(self):
        # type: (...) -> None
        self.final_output = []  # type: List
        self.final_status = []  # type: List
        self.output_dirs = set()  # type: Set

    def __call__(self, *args, **kwargs):
        return self.execute(*args, **kwargs)

    def output_callback(self, out, process_status):
        """ Collect the final status and outputs. """
        self.final_status.append(process_status)
        self.final_output.append(out)

    @abstractmethod
    def run_jobs(self,
                 process,           # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 logger,
                 runtimeContext     # type: RuntimeContext
                ):  # type: (...) -> None
        """ Execute the jobs for the given Process. """
        pass

    def execute(self,
                process,           # type: Process
                job_order_object,  # type: Dict[Text, Any]
                runtimeContext,    # type: RuntimeContext
                logger=_logger,
               ):  # type: (...) -> Tuple[Optional[Dict[Text, Any]], Text]
        """ Execute the process. """

        if not runtimeContext.basedir:
            raise WorkflowException("Must provide 'basedir' in runtimeContext")

        finaloutdir = None  # Type: Optional[Text]
        original_outdir = runtimeContext.outdir
        if isinstance(original_outdir, string_types):
            finaloutdir = os.path.abspath(original_outdir)
        runtimeContext = runtimeContext.copy()
        runtimeContext.outdir = tempfile.mkdtemp(
            prefix=getdefault(runtimeContext.tmp_outdir_prefix, DEFAULT_TMP_PREFIX))
        self.output_dirs.add(runtimeContext.outdir)
        runtimeContext.mutation_manager = MutationManager()
        runtimeContext.toplevel = True
        runtimeContext.workflow_eval_lock = threading.Condition(threading.RLock())

        job_reqs = None
        if "cwl:requirements" in job_order_object:
            job_reqs = job_order_object["cwl:requirements"]
        elif ("cwl:defaults" in process.metadata
              and "cwl:requirements" in process.metadata["cwl:defaults"]):
            job_reqs = process.metadata["cwl:defaults"]["cwl:requirements"]
        if job_reqs:
            for req in job_reqs:
                process.requirements.append(req)

        self.run_jobs(process, job_order_object, logger, runtimeContext)

        if self.final_output and self.final_output[0] and finaloutdir:
            self.final_output[0] = relocateOutputs(
                self.final_output[0], finaloutdir, self.output_dirs,
                runtimeContext.move_outputs, runtimeContext.make_fs_access(""),
                getdefault(runtimeContext.compute_checksum, True))

        if runtimeContext.rm_tmpdir:
            cleanIntermediate(self.output_dirs)

        if self.final_output and self.final_status:

            if runtimeContext.research_obj is not None and \
                    isinstance(process, (JobBase, Process, WorkflowJobStep,
                                         WorkflowJob)) and process.parent_wf:
                process_run_id = None
                name = "primary"
                process.parent_wf.generate_output_prov(self.final_output[0],
                                                       process_run_id, name)
                process.parent_wf.document.wasEndedBy(
                    process.parent_wf.workflow_run_uri, None, process.parent_wf.engine_uuid,
                    datetime.datetime.now())
                process.parent_wf.finalize_prov_profile(name)
            return (self.final_output[0], self.final_status[0])
        return (None, "permanentFail")


class SingleJobExecutor(JobExecutor):
    """ Default single-threaded CWL reference executor. """
    def run_jobs(self,
                 process,           # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 logger,
                 runtimeContext     # type: RuntimeContext
                ):  # type: (...) -> None

        process_run_id = None  # type: Optional[str]
        reference_locations = {}  # type: Dict[Text,Text]

        # define provenance profile for single commandline tool
        if not isinstance(process, Workflow) \
                and runtimeContext.research_obj is not None:
            orcid = runtimeContext.orcid
            full_name = runtimeContext.cwl_full_name
            process.provenance_object = CreateProvProfile(
                runtimeContext.research_obj, orcid, full_name)
            process.parent_wf = process.provenance_object
        jobiter = process.job(job_order_object, self.output_callback, runtimeContext)

        try:
            for job in jobiter:
                if job:
                    if runtimeContext.builder is not None:
                        job.builder = runtimeContext.builder
                    if job.outdir:
                        self.output_dirs.add(job.outdir)
                    if runtimeContext.research_obj is not None:
                        if not isinstance(process, Workflow):
                            runtimeContext.prov_obj = process.provenance_object
                        else:
                            runtimeContext.prov_obj = job.prov_obj
                        assert runtimeContext.prov_obj
                        process_run_id, reference_locations = \
                                runtimeContext.prov_obj.evaluate(
                                        process, job, job_order_object,
                                        runtimeContext.make_fs_access,
                                        runtimeContext)
                        runtimeContext = runtimeContext.copy()
                        runtimeContext.process_run_id = process_run_id
                        runtimeContext.reference_locations = \
                            reference_locations
                    job.run(runtimeContext)
                else:
                    logger.error("Workflow cannot make any more progress.")
                    break
        except (ValidationException, WorkflowException):
            raise
        except Exception as e:
            logger.exception("Got workflow error")
            raise WorkflowException(Text(e))


class MultithreadedJobExecutor(JobExecutor):
    """
    Experimental multi-threaded CWL executor.

    Does simple resource accounting, will not start a job unless it
    has cores / ram available, but does not make any attempt to
    optimize usage.
    """

    def __init__(self):  # type: () -> None
        super(MultithreadedJobExecutor, self).__init__()
        self.threads = set()  # type: Set[threading.Thread]
        self.exceptions = []  # type: List[WorkflowException]
        self.pending_jobs = []  # type: List[JobBase]

        self.max_ram = psutil.virtual_memory().total / 2**20
        self.max_cores = psutil.cpu_count()
        self.allocated_ram = 0
        self.allocated_cores = 0

    def select_resources(self, request, runtimeContext):
        result = {}
        maxrsc = {
            "cores": self.max_cores,
            "ram": self.max_ram
        }
        for rsc in ("cores", "ram"):
            if request[rsc+"Min"] > maxrsc[rsc]:
                raise WorkflowException("Requested at least %d %s but only %d available", request[rsc+"Min"], rsc, maxrsc[rsc])
            if request[rsc+"Max"] < maxrsc[rsc]:
                result[rsc] = request[rsc+"Max"]
            else:
                result[rsc] = maxrsc[rsc]

        return result

    def run_job(self,
                job,      # type: JobBase
                runtimeContext  # type: RuntimeContext
               ):  # type: (...) -> None
        """ Execute a single Job in a seperate thread. """

        if job is not None:
            self.pending_jobs.append(job)

        while self.pending_jobs:
            job = self.pending_jobs[0]
            if isinstance(job, JobBase):
                if ((self.allocated_ram + job.builder.resources["ram"]) > self.max_ram or
                    (self.allocated_cores + job.builder.resources["cores"]) > self.max_cores):
                    return

            self.pending_jobs.pop(0)

            def runner():
                """ Job running thread. """
                try:
                    job.run(runtimeContext)
                except WorkflowException as err:
                    _logger.exception("Got workflow error")
                    self.exceptions.append(err)
                except Exception as err:
                    _logger.exception("Got workflow error")
                    self.exceptions.append(WorkflowException(Text(err)))
                finally:
                    with runtimeContext.workflow_eval_lock:
                        self.threads.remove(thread)
                        if isinstance(job, JobBase):
                            self.allocated_ram -= job.builder.resources["ram"]
                            self.allocated_cores -= job.builder.resources["cores"]
                        runtimeContext.workflow_eval_lock.notifyAll()

            thread = threading.Thread(target=runner)
            thread.daemon = True
            self.threads.add(thread)
            if isinstance(job, JobBase):
                self.allocated_ram += job.builder.resources["ram"]
                self.allocated_cores += job.builder.resources["cores"]
            thread.start()

    def wait_for_next_completion(self, runtimeContext):  # type: (RuntimeContext) -> None
        """ Wait for jobs to finish. """
        if runtimeContext.workflow_eval_lock is not None:
            runtimeContext.workflow_eval_lock.wait()
        if self.exceptions:
            raise self.exceptions[0]

    def run_jobs(self,
                 process,           # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 logger,
                 runtimeContext     # type: RuntimeContext
                ):  # type: (...) -> None

        jobiter = process.job(job_order_object, self.output_callback, runtimeContext)

        if runtimeContext.workflow_eval_lock is None:
            raise WorkflowException("runtimeContext.workflow_eval_lock must not be None")

        runtimeContext.workflow_eval_lock.acquire()
        for job in jobiter:
            if job is not None:
                if runtimeContext.builder is not None:
                    job.builder = runtimeContext.builder
                if job.outdir:
                    self.output_dirs.add(job.outdir)

            self.run_job(job, runtimeContext)

            if job is None:
                if self.threads:
                    self.wait_for_next_completion(runtimeContext)
                else:
                    logger.error("Workflow cannot make any more progress.")
                    break

        while self.threads:
            self.wait_for_next_completion(runtimeContext)
