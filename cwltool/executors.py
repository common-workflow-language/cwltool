import logging
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

from .builder import Builder  # pylint: disable=unused-import
from .errors import WorkflowException
from .job import JobBase  # pylint: disable=unused-import
from .mutation import MutationManager
from .provenance import create_ProvProfile
from .process import (Process,  # pylint: disable=unused-import
                      cleanIntermediate, relocateOutputs)
from .utils import DEFAULT_TMP_PREFIX
from .context import LoadingContext, RuntimeContext, getdefault
from .workflow import Workflow

_logger = logging.getLogger("cwltool")

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

            if runtimeContext.research_obj is not None and hasattr(process, 'parent_wf') and process.parent_wf:
                ProcessRunID=None
                name="primary"
                process.parent_wf.generate_outputProv(self.final_output[0], ProcessRunID)
                process.parent_wf.document.wasEndedBy(
                    process.parent_wf.workflowRunURI, None, process.parent_wf.engineUUID,
                    datetime.datetime.now())
                process.parent_wf.finalize_provProfile(name)
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
        provObj=None  # type: Any
        ProcessRunID=None  # type: str
        reference_locations={}  # type: Dict[Text,Text]

        # define provenance profile for single commandline tool
        if not isinstance(process, Workflow) \
                and runtimeContext.research_obj is not None:
            orcid=runtimeContext.orcid
            full_name=runtimeContext.cwl_full_name
            process.provenanceObject=create_ProvProfile(runtimeContext.research_obj, orcid, full_name)
            proces.parent_wf=process.provenanceObject
            provObj=process.provenanceObject
        jobiter = process.job(job_order_object, self.output_callback, runtimeContext)

        try:
            for job in jobiter:
                if job:
                    if runtimeContext.builder is not None:
                        job.builder = runtimeContext.builder
                    if job.outdir:
                        self.output_dirs.add(job.outdir)
                    if runtimeContext.research_obj is not None \
                            and runtimeContext.research_obj \
                            and hasattr(job, 'provObj') and job.provObj:
                        if not isinstance(process, Workflow):
                            provObj=t.provenanceObject
                        else:
                            provObj=r.provObj
                        ProcessRunID, reference_locations = provObj._evaluate(
                            proces, job, job_order_object, make_fs_access,
                            runtimeContext)
                        runtimeContext=runtimeContext.copy()
                        job.run(ProcessRunID, reference_locations, **kwargs)
                    else:
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

    Can easily overload a system as it does not do resource accounting.
    """
    def __init__(self):  # type: () -> None
        super(MultithreadedJobExecutor, self).__init__()
        self.threads = set()  # type: Set[threading.Thread]
        self.exceptions = []  # type: List[WorkflowException]

    def run_job(self,
                job,      # type: JobBase
                runtimeContext  # type: RuntimeContext
               ):  # type: (...) -> None
        """ Execute a single Job in a seperate thread. """
        def runner():
            """ Job running thread. """
            try:
                job.run(runtimeContext)
            except WorkflowException as err:
                self.exceptions.append(err)
            except Exception as err:
                self.exceptions.append(WorkflowException(Text(err)))
            self.threads.remove(thread)

        thread = threading.Thread(target=runner)
        thread.daemon = True
        self.threads.add(thread)
        thread.start()

    def wait_for_next_completion(self):  # type: () -> None
        """ Check for exceptions while waiting for the jobs to finish. """
        if self.exceptions:
            raise self.exceptions[0]

    def run_jobs(self,
                 process,           # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 logger,
                 runtimeContext     # type: RuntimeContext
                ):  # type: (...) -> None

        jobiter = process.job(job_order_object, self.output_callback, runtimeContext)

        for job in jobiter:
            if job:
                if runtimeContext.builder is not None:
                    job.builder = runtimeContext.builder
                if job.outdir:
                    self.output_dirs.add(job.outdir)
                self.run_job(job, runtimeContext)
            else:
                if self.threads:
                    self.wait_for_next_completion()
                else:
                    logger.error("Workflow cannot make any more progress.")
                    break

        while self.threads:
            self.wait_for_next_completion()
