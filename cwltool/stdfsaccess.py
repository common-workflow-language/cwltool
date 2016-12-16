from typing import Any, BinaryIO, Text
from .pathmapper import abspath
import glob
import os

class StdFsAccess(object):

    def __init__(self, basedir):  # type: (Text) -> None
        self.basedir = basedir

    def _abs(self, p):  # type: (Text) -> Text
        return abspath(p, self.basedir)

    def glob(self, pattern):  # type: (Text) -> List[Text]
        return ["file://%s" % self._abs(l) for l in glob.glob(self._abs(pattern))]

    def open(self, fn, mode):  # type: (Text, Text) -> BinaryIO
        return open(self._abs(fn), mode)

    def exists(self, fn):  # type: (Text) -> bool
        return os.path.exists(self._abs(fn))

    def isfile(self, fn):  # type: (Text) -> bool
        return os.path.isfile(self._abs(fn))

    def isdir(self, fn):  # type: (Text) -> bool
        return os.path.isdir(self._abs(fn))

    def listdir(self, fn):  # type: (Text) -> List[Text]
        return [abspath(l, fn) for l in os.listdir(self._abs(fn))]

    def join(self, path, *paths):  # type: (Text, *Text) -> Text
        return os.path.join(path, *paths)

    def realpath(self, path):  # type: (Text) -> Text
        return os.path.realpath(path)
