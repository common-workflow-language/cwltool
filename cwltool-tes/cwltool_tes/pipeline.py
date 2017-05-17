import time
import logging
import cwltool.workflow
from pprint import pformat

from cwltool.errors import WorkflowException

log = logging.getLogger('funnel')


class Pipeline(object):

    def __init__(self):
        self.threads = []

    def executor(self, tool, job_order, **kwargs):
        log.debug(kwargs)

        kwargs = self.configure(kwargs)
        jobs = tool.job(job_order, self.output_callback, **kwargs)

        try:
            for runnable in jobs:
                if runnable:
                    runnable.run(**kwargs)
                else:
                    time.sleep(1)
        except WorkflowException:
            raise
        except Exception as e:
            log.exception('workflow error')
            raise WorkflowException(unicode(e))

        self.wait()
        log.info('all processes have joined')
        log.info(self.output)

        return self.output

    def make_exec_tool(self, spec, **kwargs):
        raise Exception("Pipeline.make_exec_tool() not implemented")

    def make_tool(self, spec, **kwargs):
        if 'class' in spec and spec['class'] == 'CommandLineTool':
            return self.make_exec_tool(spec, **kwargs)
        else:
            return cwltool.workflow.defaultMakeTool(spec, **kwargs)

    def add_thread(self, thread):
        self.threads.append(thread)

    def wait(self):
        for i in self.threads:
            i.join()

    def output_callback(self, out, status):
        if status == 'success':
            log.info('Job completed!')
        else:
            log.info('Job failed...')
        log.debug("job done" + pformat(out) + status)
        self.output = out


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
