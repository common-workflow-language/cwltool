from typing import Any, IO
from .pathmapper import abspath
import glob
import os


class StdFsAccess(object):

    def __init__(self, basedir):  # type: (str) -> None
        self.basedir = basedir

    def _abs(self, p):  # type: (str) -> str
        return abspath(p, self.basedir)

    def glob(self, pattern):  # type: (str) -> List[str]
        return glob.glob(self._abs(pattern))

    def open(self, fn, mode):  # type: (str, str) -> IO[Any]
        return open(self._abs(fn), mode)

    def exists(self, fn):  # type: (str) -> bool
        return os.path.exists(self._abs(fn))
