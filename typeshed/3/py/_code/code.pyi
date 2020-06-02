from typing import Any, Optional

builtin_repr = repr
reprlib: Any

class Code:
    filename: Any = ...
    firstlineno: Any = ...
    name: Any = ...
    raw: Any = ...
    def __init__(self, rawcode: Any) -> None: ...
    def __eq__(self, other: Any) -> Any: ...
    def __ne__(self, other: Any) -> Any: ...
    @property
    def path(self): ...
    @property
    def fullsource(self): ...
    def source(self): ...
    def getargs(self, var: bool = ...): ...

class Frame:
    lineno: Any = ...
    f_globals: Any = ...
    f_locals: Any = ...
    raw: Any = ...
    code: Any = ...
    def __init__(self, frame: Any) -> None: ...
    @property
    def statement(self): ...
    def eval(self, code: Any, **vars: Any): ...
    def exec_(self, code: Any, **vars: Any) -> None: ...
    def repr(self, object: Any): ...
    def is_true(self, object: Any): ...
    def getargs(self, var: bool = ...): ...

class TracebackEntry:
    exprinfo: Any = ...
    lineno: Any = ...
    def __init__(self, rawentry: Any) -> None: ...
    def set_repr_style(self, mode: Any) -> None: ...
    @property
    def frame(self): ...
    @property
    def relline(self): ...
    @property
    def statement(self): ...
    @property
    def path(self): ...
    def getlocals(self): ...
    locals: Any = ...
    def reinterpret(self): ...
    def getfirstlinesource(self): ...
    def getsource(self, astcache: Optional[Any] = ...): ...
    source: Any = ...
    def ishidden(self): ...
    def name(self): ...
    name: Any = ...

class Traceback(list):
    Entry: Any = ...
    def __init__(self, tb: Any) -> None: ...
    def cut(self, path: Optional[Any] = ..., lineno: Optional[Any] = ..., firstlineno: Optional[Any] = ..., excludepath: Optional[Any] = ...): ...
    def __getitem__(self, key: Any): ...
    def filter(self, fn: Any = ...): ...
    def getcrashentry(self): ...
    def recursionindex(self): ...

co_equal: Any

class ExceptionInfo:
    type: Any = ...
    value: Any = ...
    tb: Any = ...
    typename: Any = ...
    traceback: Any = ...
    def __init__(self, tup: Optional[Any] = ..., exprinfo: Optional[Any] = ...) -> None: ...
    def exconly(self, tryshort: bool = ...): ...
    def errisinstance(self, exc: Any): ...
    def getrepr(self, showlocals: bool = ..., style: str = ..., abspath: bool = ..., tbfilter: bool = ..., funcargs: bool = ...): ...
    def __unicode__(self): ...

class FormattedExcinfo:
    flow_marker: str = ...
    fail_marker: str = ...
    showlocals: Any = ...
    style: Any = ...
    tbfilter: Any = ...
    funcargs: Any = ...
    abspath: Any = ...
    astcache: Any = ...
    def __init__(self, showlocals: bool = ..., style: str = ..., abspath: bool = ..., tbfilter: bool = ..., funcargs: bool = ...) -> None: ...
    def repr_args(self, entry: Any): ...
    def get_source(self, source: Any, line_index: int = ..., excinfo: Optional[Any] = ..., short: bool = ...): ...
    def get_exconly(self, excinfo: Any, indent: int = ..., markall: bool = ...): ...
    def repr_locals(self, locals: Any): ...
    def repr_traceback_entry(self, entry: Any, excinfo: Optional[Any] = ...): ...
    def repr_traceback(self, excinfo: Any): ...
    def repr_excinfo(self, excinfo: Any): ...

class TerminalRepr:
    def __unicode__(self): ...

class ReprExceptionInfo(TerminalRepr):
    reprtraceback: Any = ...
    reprcrash: Any = ...
    sections: Any = ...
    def __init__(self, reprtraceback: Any, reprcrash: Any) -> None: ...
    def addsection(self, name: Any, content: Any, sep: str = ...) -> None: ...
    def toterminal(self, tw: Any) -> None: ...

class ReprTraceback(TerminalRepr):
    entrysep: str = ...
    reprentries: Any = ...
    extraline: Any = ...
    style: Any = ...
    def __init__(self, reprentries: Any, extraline: Any, style: Any) -> None: ...
    def toterminal(self, tw: Any) -> None: ...

class ReprTracebackNative(ReprTraceback):
    style: str = ...
    reprentries: Any = ...
    extraline: Any = ...
    def __init__(self, tblines: Any) -> None: ...

class ReprEntryNative(TerminalRepr):
    style: str = ...
    lines: Any = ...
    def __init__(self, tblines: Any) -> None: ...
    def toterminal(self, tw: Any) -> None: ...

class ReprEntry(TerminalRepr):
    localssep: str = ...
    lines: Any = ...
    reprfuncargs: Any = ...
    reprlocals: Any = ...
    reprfileloc: Any = ...
    style: Any = ...
    def __init__(self, lines: Any, reprfuncargs: Any, reprlocals: Any, filelocrepr: Any, style: Any) -> None: ...
    def toterminal(self, tw: Any) -> None: ...

class ReprFileLocation(TerminalRepr):
    path: Any = ...
    lineno: Any = ...
    message: Any = ...
    def __init__(self, path: Any, lineno: Any, message: Any) -> None: ...
    def toterminal(self, tw: Any) -> None: ...

class ReprLocals(TerminalRepr):
    lines: Any = ...
    def __init__(self, lines: Any) -> None: ...
    def toterminal(self, tw: Any) -> None: ...

class ReprFuncArgs(TerminalRepr):
    args: Any = ...
    def __init__(self, args: Any) -> None: ...
    def toterminal(self, tw: Any) -> None: ...

oldbuiltins: Any

def patch_builtins(assertion: bool = ..., compile: bool = ...) -> None: ...
def unpatch_builtins(assertion: bool = ..., compile: bool = ...) -> None: ...
def getrawcode(obj: Any, trycall: bool = ...): ...
