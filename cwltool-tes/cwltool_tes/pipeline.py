import logging
import os
import tempfile
import time

from pprint import pformat

from cwltool.errors import WorkflowException
from cwltool.process import cleanIntermediate, relocateOutputs
from cwltool.mutation import MutationManager

log = logging.getLogger('funnel')


class Pipeline(object):

    def __init__(self):
        self.threads = []

    def executor(self, tool, job_order, **kwargs):
        final_output = []
        final_status = []

        def output_callback(out, processStatus):
            final_status.append(processStatus)
            final_output.append(out)

        if "basedir" not in kwargs:
            raise WorkflowException("Must provide 'basedir' in kwargs")

        output_dirs = set()
        finaloutdir = os.path.abspath(kwargs.get("outdir")) if kwargs.get("outdir") else None
        kwargs["outdir"] = tempfile.mkdtemp(prefix=kwargs["tmp_outdir_prefix"]) if kwargs.get(
            "tmp_outdir_prefix") else tempfile.mkdtemp()
        output_dirs.add(kwargs["outdir"])
        kwargs["mutation_manager"] = MutationManager()

        jobReqs = None
        if "cwl:requirements" in job_order:
            jobReqs = job_order["cwl:requirements"]
        elif ("cwl:defaults" in tool.metadata and "cwl:requirements" in tool.metadata["cwl:defaults"]):
            jobReqs = tool.metadata["cwl:defaults"]["cwl:requirements"]
        if jobReqs:
            for req in jobReqs:
                tool.requirements.append(req)

        if kwargs.get("default_container"):
            tool.requirements.insert(0, {
                "class": "DockerRequirement",
                "dockerPull": kwargs["default_container"]
            })

        jobs = tool.job(job_order, output_callback, **kwargs)
        try:
            for runnable in jobs:
                if runnable:
                    if runnable.outdir:
                        output_dirs.add(runnable.outdir)
                    runnable.run(**kwargs)
                else:
                    time.sleep(1)
        except WorkflowException:
            raise e
        except Exception as e:
            log.exception('workflow error')
            raise WorkflowException(unicode(e))

        self.wait()

        if final_output and final_output[0] and finaloutdir:
            final_output[0] = relocateOutputs(
                final_output[0], finaloutdir,
                output_dirs, kwargs.get("move_outputs"),
                kwargs["make_fs_access"](""))

        if kwargs.get("rm_tmpdir"):
            cleanIntermediate(output_dirs)

        if final_output and final_status:
            return (final_output[0], final_status[0])
        else:
            return (None, "permanentFail")


    def make_exec_tool(self, spec, **kwargs):
        raise Exception("Pipeline.make_exec_tool() not implemented")

    def make_tool(self, spec, **kwargs):
        raise Exception("Pipeline.make_tool() not implemented")

    def add_thread(self, thread):
        self.threads.append(thread)

    def wait(self):
        for i in self.threads:
            i.join()


class PipelineJob(object):

    def __init__(self, spec, pipeline):
        self.spec = spec
        self.pipeline = pipeline
        self.running = False

    def find_docker_requirement(self):
        default = "python:2.7"
        container = default
        if self.pipeline.kwargs["default_container"]:
            container = self.pipeline.kwargs["default_container"]

        reqs = self.spec.get("requirements", []) + self.spec.get("hints", [])
        for i in reqs:
            if i.get("class", "NA") == "DockerRequirement":
                container = i.get("dockerPull", i.get("dockerImageId", default))
        return container

    def run(self, pull_image=True, rm_container=True, rm_tmpdir=True,
            move_outputs="move", **kwargs):
        raise Exception("PipelineJob.run() not implemented")
