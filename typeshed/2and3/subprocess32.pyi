# Stubs for subprocess32 3.5.0-rc1
# adapted from
# https://github.com/python/typeshed/blob/8e62a79970227aa331f8070e64151002b7dfddea/stdlib/3/subprocess.pyi
# From the subprocess32 README
# > Timeout support backported from Python 3.3 is included.
# > The run() API from Python 3.5 was backported
# > Otherwise features are frozen at the 3.2 level.

import sys
from typing import Sequence, Any, Mapping, Callable, Tuple, IO, Optional, Union, List, Type, Text
from types import TracebackType

# We prefer to annotate inputs to methods (eg subprocess.check_call) with these
# union types. However, outputs (eg check_call return) and class attributes
# (eg TimeoutError.cmd) we prefer to annotate with Any, so the caller does not
# have to use an assertion to confirm which type.
#
# For example:
#
# try:
#    x = subprocess.check_output(["ls", "-l"])
#    reveal_type(x)  # Any, but morally is _TXT
# except TimeoutError as e:
#    reveal_type(e.cmd)  # Any, but morally is _CMD
_FILE = Union[None, int, IO[Any]]
_TXT = Union[bytes, Text]
_PATH = Union[bytes, Text]
_CMD = Union[_TXT, Sequence[_PATH]]
_ENV = Union[Mapping[bytes, _TXT], Mapping[Text, _TXT]]

class CompletedProcess:
    # morally: _CMD
    args = ...  # type: Any
    returncode = ...  # type: int
    # morally: Optional[_TXT]
    stdout = ...  # type: Any
    stderr = ...  # type: Any
    def __init__(self, args: _CMD,
                 returncode: int,
                 stdout: Optional[_TXT] = ...,
                 stderr: Optional[_TXT] = ...) -> None: ...
    def check_returncode(self) -> None: ...

# Nearly same args as Popen.__init__ except for timeout, input, and check
def run(args: _CMD,
        timeout: Optional[float] = ...,
        input: Optional[_TXT] = ...,
        check: bool = ...,
        bufsize: int = ...,
        executable: _PATH = ...,
        stdin: _FILE = ...,
        stdout: _FILE = ...,
        stderr: _FILE = ...,
        preexec_fn: Callable[[], Any] = ...,
        close_fds: bool = ...,
        shell: bool = ...,
        cwd: Optional[_PATH] = ...,
        env: Optional[_ENV] = ...,
        universal_newlines: bool = ...,
        startupinfo: Any = ...,
        creationflags: int = ...,
        restore_signals: bool = ...,
        start_new_session: bool = ...,
        pass_fds: Any = ...) -> CompletedProcess: ...

def call(args: _CMD,
         bufsize: int = ...,
         executable: _PATH = ...,
         stdin: _FILE = ...,
         stdout: _FILE = ...,
         stderr: _FILE = ...,
         preexec_fn: Callable[[], Any] = ...,
         close_fds: bool = ...,
         shell: bool = ...,
         cwd: Optional[_PATH] = ...,
         env: Optional[_ENV] = ...,
         universal_newlines: bool = ...,
         startupinfo: Any = ...,
         creationflags: int = ...,
         restore_signals: bool = ...,
         start_new_session: bool = ...,
         pass_fds: Any = ...,
         timeout: float = ...) -> int: ...

def check_call(args: _CMD,
               bufsize: int = ...,
               executable: _PATH = ...,
               stdin: _FILE = ...,
               stdout: _FILE = ...,
               stderr: _FILE = ...,
               preexec_fn: Callable[[], Any] = ...,
               close_fds: bool = ...,
               shell: bool = ...,
               cwd: Optional[_PATH] = ...,
               env: Optional[_ENV] = ...,
               universal_newlines: bool = ...,
               startupinfo: Any = ...,
               creationflags: int = ...,
               restore_signals: bool = ...,
               start_new_session: bool = ...,
               pass_fds: Any = ...,
               timeout: float = ...) -> int: ...

def check_output(args: _CMD,
                 bufsize: int = ...,
                 executable: _PATH = ...,
                 stdin: _FILE = ...,
                 stderr: _FILE = ...,
                 preexec_fn: Callable[[], Any] = ...,
                 close_fds: bool = ...,
                 shell: bool = ...,
                 cwd: Optional[_PATH] = ...,
                 env: Optional[_ENV] = ...,
                 universal_newlines: bool = ...,
                 startupinfo: Any = ...,
                 creationflags: int = ...,
                 restore_signals: bool = ...,
                 start_new_session: bool = ...,
                 pass_fds: Any = ...,
                 timeout: float = ...,
                 ) -> Any: ...  # morally: -> _TXT


PIPE = ...  # type: int
STDOUT = ...  # type: int
DEVNULL = ...  # type: int
class SubprocessError(Exception): ...
class TimeoutExpired(SubprocessError):
# morally: _CMD
	cmd = ...  # type: Any
	timeout = ...  # type: float
	# morally: Optional[_TXT]
	output = ...  # type: Any
	stdout = ...  # type: Any
	stderr = ...  # type: Any


class CalledProcessError(Exception):
    returncode = 0
    # morally: _CMD
    cmd = ...  # type: Any
    # morally: Optional[_TXT]
    output = ...  # type: Any

    stdout = ...  # type: Any
    stderr = ...  # type: Any

    def __init__(self,
                 returncode: int,
                 cmd: _CMD,
                 output: Optional[_TXT] = ...,
                 stderr: Optional[_TXT] = ...) -> None: ...

class Popen:
    args = ...  # type: _CMD
    stdin = ...  # type: IO[Any]
    stdout = ...  # type: IO[Any]
    stderr = ...  # type: IO[Any]
    pid = 0
    returncode = 0


    def __init__(self,
                 args: _CMD,
                 bufsize: int = ...,
                 executable: Optional[_PATH] = ...,
                 stdin: Optional[_FILE] = ...,
                 stdout: Optional[_FILE] = ...,
                 stderr: Optional[_FILE] = ...,
                 preexec_fn: Optional[Callable[[], Any]] = ...,
                 close_fds: bool = ...,
                 shell: bool = ...,
                 cwd: Optional[_PATH] = ...,
                 env: Optional[_ENV] = ...,
                 universal_newlines: bool = ...,
                 startupinfo: Optional[Any] = ...,
                 creationflags: int = ...,
                 restore_signals: bool = ...,
                 start_new_session: bool = ...,
                 pass_fds: Any = ...) -> None: ...

    def poll(self) -> int: ...
    def wait(self, timeout: Optional[float] = ...) -> int: ...
    # Return str/bytes
    def communicate(self,
                    input: Optional[_TXT] = ...,
                    timeout: Optional[float] = ...,
                    # morally: -> Tuple[Optional[_TXT], Optional[_TXT]]
                    ) -> Tuple[Any, Any]: ...
    def send_signal(self, signal: int) -> None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def __enter__(self) -> 'Popen': ...
    def __exit__(self, type: Optional[Type[BaseException]], value: Optional[BaseException], traceback: Optional[TracebackType]) -> bool: ...

# The result really is always a str.
def getstatusoutput(cmd: _TXT) -> Tuple[int, str]: ...
def getoutput(cmd: _TXT) -> str: ...

def list2cmdline(seq: Sequence[str]) -> str: ...  # undocumented
