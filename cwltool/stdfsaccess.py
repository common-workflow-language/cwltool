from typing import Any, BinaryIO
from .pathmapper import abspath
import glob
import os


class StdFsAccess(object):

    def __init__(self, basedir):  # type: (unicode) -> None
        self.basedir = basedir

    def _abs(self, p):  # type: (unicode) -> unicode
        return abspath(p, self.basedir)

    def glob(self, pattern):  # type: (unicode) -> List[unicode]
        return glob.glob(self._abs(pattern))

    def open(self, fn, mode):  # type: (unicode, str) -> BinaryIO
        return open(self._abs(fn), mode)

    def exists(self, fn):  # type: (unicode) -> bool
        return os.path.exists(self._abs(fn))
