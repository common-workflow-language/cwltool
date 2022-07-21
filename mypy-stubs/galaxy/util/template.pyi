from . import unicodify as unicodify
from Cheetah.Compiler import Compiler
from _typeshed import Incomplete

refactoring_tool: Incomplete

class FixedModuleCodeCompiler(Compiler):
    module_code: Incomplete
    def getModuleCode(self): ...

def create_compiler_class(module_code): ...
def fill_template(
    template_text,
    context: Incomplete | None = ...,
    retry: int = ...,
    compiler_class=...,
    first_exception: Incomplete | None = ...,
    futurized: bool = ...,
    python_template_version: str = ...,
    **kwargs
): ...
def futurize_preprocessor(source): ...
