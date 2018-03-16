import logging
import tempfile
import threading

import os
import copy
import uuid
import datetime
import time
from abc import ABCMeta, abstractmethod
import prov.model as prov
from typing import Dict, Text, Any, Tuple, Set, List


from .builder import Builder
from .errors import WorkflowException
from .mutation import MutationManager
from .job import JobBase
from .process import relocateOutputs, cleanIntermediate, Process, shortname, uniquename, get_overrides
from . import loghandler
from schema_salad.sourceline import SourceLine

_logger = logging.getLogger("cwltool")

class JobExecutor(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        # type: (...) -> None
        self.final_output = []  # type: List
        self.final_status = []  # type: List
        self.output_dirs = set()  # type: Set

    def __call__(self, *args, **kwargs):
        return self.execute(*args, **kwargs)

    def output_callback(self, out, processStatus):
        self.final_status.append(processStatus)
        self.final_output.append(out)

    @abstractmethod
    def run_jobs(self,
                 t,  # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 document,
                 engineUUID,
                 WorkflowRunID,
                 logger,
                 **kwargs  # type: Any
                 ):
        pass

    def execute(self, t,  # type: Process
                job_order_object,  # type: Dict[Text, Any]
                logger=_logger,
                provDoc=None,
                engineID=None,
                WorkflowID=None,
                **kwargs  # type: Any
                ):
        # type: (...) -> Tuple[Dict[Text, Any], Text]

        if "basedir" not in kwargs:
            raise WorkflowException("Must provide 'basedir' in kwargs")

        finaloutdir = os.path.abspath(kwargs.get("outdir")) if kwargs.get("outdir") else None
        kwargs["outdir"] = tempfile.mkdtemp(prefix=kwargs["tmp_outdir_prefix"]) if kwargs.get(
            "tmp_outdir_prefix") else tempfile.mkdtemp()
        self.output_dirs.add(kwargs["outdir"])
        kwargs["mutation_manager"] = MutationManager()

        jobReqs = None
        if "cwl:requirements" in job_order_object:
            jobReqs = job_order_object["cwl:requirements"]
        elif ("cwl:defaults" in t.metadata and "cwl:requirements" in t.metadata["cwl:defaults"]):
            jobReqs = t.metadata["cwl:defaults"]["cwl:requirements"]
        if jobReqs:
            for req in jobReqs:
                t.requirements.append(req)

        self.run_jobs(t, job_order_object, provDoc, engineID, WorkflowID, logger, **kwargs)

        if self.final_output and self.final_output[0] and finaloutdir:
            self.final_output[0] = relocateOutputs(
                self.final_output[0], finaloutdir, self.output_dirs,
                kwargs.get("move_outputs"), kwargs["make_fs_access"](""),
                kwargs.get("compute_checksum", True))

        if kwargs.get("rm_tmpdir"):
            cleanIntermediate(self.output_dirs)

        if self.final_output and self.final_status:
            return (self.final_output[0], self.final_status[0])
        else:
            return (None, "permanentFail")


class SingleJobExecutor(JobExecutor):
    def run_jobs(self,
                 t,  # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 document,
                 engineUUID,
                 WorkflowRunID,
                 logger,
                 **kwargs  # type: Any
                 ):
        reference_locations={} # type: Dict[Text, Any]
        ProcessProvActivity=''
        jobiter = t.job(job_order_object,
                        self.output_callback,
                        **kwargs)
        try:
            research_obj = kwargs.get("research_obj")
            for r in jobiter:
                if r:
                    builder = kwargs.get("builder", None)  # type: Builder

                    if builder is not None:
                        r.builder = builder
                    if r.outdir:
                        self.output_dirs.add(r.outdir)
                    if research_obj:
                        #here we are recording provenance of each subprocess of the workflow
                        if ".cwl" in getattr(r, "name") or "workflow main" in getattr(r, "name"): #for prospective provenance NOTE: the second condition is for packed file
                            steps=[]
                            for s in r.steps:
                                stepname="wf:main/"+str(s.name)[5:]
                                steps.append(stepname)
                                document.entity(stepname, {prov.PROV_TYPE: "wfdesc:Process", "prov:type": "prov:Plan"})
                            #create prospective provenance recording for the workflow
                            document.entity("wf:main", {prov.PROV_TYPE: "wfdesc:Process", "prov:type": "prov:Plan", "wfdesc:hasSubProcess=":str(steps),  "prov:label":"Prospective provenance"})
                            customised_job={} #new job object for RO
                            for e, i in enumerate(r.tool["inputs"]):
                                with SourceLine(r.tool["inputs"], e, WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
                                    iid = shortname(i["id"])
                                    if iid in job_order_object:
                                        customised_job[iid]= copy.deepcopy(job_order_object[iid]) #add the input element in dictionary for provenance
                                    elif "default" in i:
                                        customised_job[iid]= copy.deepcopy(i["default"]) #add the defualt elements in the dictionary for provenance
                                    else:
                                        raise WorkflowException(
                                            u"Input '%s' not in input object and does not have a default value." % (i["id"]))
                            ##create master-job.json and returns a dictionary with workflow level identifiers as keys and locations or actual values of the attributes as values.
                            relativised_input_object=research_obj.create_job(customised_job, kwargs) #call the method to generate a file with customised job

                            for key, value in relativised_input_object.items():
                                strvalue=str(value)
                                if "Data" in strvalue:
                                    shahash="data:"+value.split("/")[-1]
                                    rel_path=value[3:]
                                    reference_locations[job_order_object[key]["location"]]=relativised_input_object[key][11:]
                                    document.entity(shahash, {prov.PROV_TYPE:"wfprov:Artifact"})
                                    #document.specializationOf(rel_path, shahash) NOTE:THIS NEEDS FIXING as it required both params as entities.
                                else:
                                    ArtefactValue="data:"+strvalue
                                    document.entity(ArtefactValue, {prov.PROV_TYPE:"wfprov:Artifact"})
                        else:
                            ProcessRunID="run:"+str(uuid.uuid4())
                            #each subprocess is defined as an activity()
                            provLabel="Run of workflow/packed.cwl#main/"+str(r.name)
                            ProcessProvActivity = document.activity(ProcessRunID, None, None, {prov.PROV_TYPE: "wfprov:ProcessRun", "prov:label": provLabel})
                            if hasattr(r, 'name') and ".cwl" not in getattr(r, "name") and "workflow main" not in getattr(r, "name"):
                                document.wasAssociatedWith(ProcessRunID, engineUUID, str("wf:main/"+r.name))
                            document.wasStartedBy(ProcessRunID, None, WorkflowRunID, datetime.datetime.now(), None, None)
                            #this is where you run each step. so start and end time for the step
                    if research_obj:
                        r.run(document, WorkflowRunID, ProcessProvActivity, reference_locations, **kwargs)
                    else:
                        r.run(**kwargs)
                        #capture workflow level outputs in the prov doc
                    if research_obj:
                        for eachOutput in self.final_output:
                            for key, value in eachOutput.items():
                                outputProvRole="wf:main"+"/"+str(key)
                                output_checksum="data:"+str(value["checksum"][5:])
                                document.entity(output_checksum, {prov.PROV_TYPE:"wfprov:Artifact"})
                                document.wasGeneratedBy(output_checksum, WorkflowRunID, datetime.datetime.now(), None, {"prov:role":outputProvRole })
                else:
                    logger.error("Workflow cannot make any more progress.")
                    break
        except WorkflowException:
            raise
        except Exception as e:
            logger.exception("Got workflow error")
            raise WorkflowException(Text(e))


class MultithreadedJobExecutor(JobExecutor):
    def __init__(self):
        super(MultithreadedJobExecutor, self).__init__()
        self.threads = set()
        self.exceptions = []

    def run_job(self,
                job,      # type: JobBase
                **kwargs  # type: Any
                ):
        # type: (...) -> None
        def runner():
            try:
                job.run(**kwargs)
            except WorkflowException as e:
                self.exceptions.append(e)
            except Exception as e:
                self.exceptions.append(WorkflowException(Text(e)))

            self.threads.remove(thread)

        thread = threading.Thread(target=runner)
        thread.daemon = True
        self.threads.add(thread)
        thread.start()

    def wait_for_next_completion(self):  # type: () -> None
        if self.exceptions:
            raise self.exceptions[0]

    def run_jobs(self,
                 t,  # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 document,
                 engineUUID,
                 WorkflowRunID,
                 logger,
                 **kwargs  # type: Any
                 ):

        jobiter = t.job(job_order_object, self.output_callback, **kwargs)

        for r in jobiter:
            if r:
                builder = kwargs.get("builder", None)  # type: Builder
                if builder is not None:
                    r.builder = builder
                if r.outdir:
                    self.output_dirs.add(r.outdir)
                self.run_job(r, **kwargs)
            else:
                if len(self.threads):
                    self.wait_for_next_completion()
                else:
                    logger.error("Workflow cannot make any more progress.")
                    break

        while len(self.threads) > 0:
            self.wait_for_next_completion()
