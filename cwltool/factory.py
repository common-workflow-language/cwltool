import main
import workflow
import os

class Callable(object):
    def __init__(self, t, factory):
        self.t = t
        self.factory = factory

    def __call__(self, **kwargs):
        return self.factory.executor(self.t, kwargs, os.getcwd(), None, **self.factory.execkwargs)

class Factory(object):
    def __init__(self, makeTool=workflow.defaultMakeTool,
                 executor=main.single_job_executor,
                 **execkwargs):
        self.makeTool = makeTool
        self.executor = executor
        self.execkwargs = execkwargs

    def make(self, cwl):
        l = main.load_tool(cwl, False, True, self.makeTool, False)
        if type(l) == int:
            raise Exception()
        return Callable(l, self)
