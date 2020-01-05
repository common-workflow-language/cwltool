"""Abstracted IO access."""

import glob
import os
import urllib
from io import open
from typing import IO, Any, List

from schema_salad.ref_resolver import file_uri, uri_file_path

from .utils import onWindows


def abspath(src, basedir):  # type: (str, str) -> str
    if src.startswith("file://"):
        abpath = str(uri_file_path(str(src)))
    elif urllib.parse.urlsplit(src).scheme in ["http", "https"]:
        return src
    else:
        if basedir.startswith("file://"):
            abpath = src if os.path.isabs(src) else basedir + "/" + src
        else:
            abpath = src if os.path.isabs(src) else os.path.join(basedir, src)
    return abpath


class StdFsAccess(object):
    """Local filesystem implementation."""

    def __init__(self, basedir):  # type: (str) -> None
        """Perform operations with respect to a base directory."""
        self.basedir = basedir

    def _abs(self, p):  # type: (str) -> str
        return abspath(p, self.basedir)

    def glob(self, pattern):  # type: (str) -> List[str]
        return [file_uri(str(self._abs(l))) for l in glob.glob(self._abs(pattern))]

    def open(self, fn, mode):  # type: (str, str) -> IO[Any]
        return open(self._abs(fn), mode)

    def exists(self, fn):  # type: (str) -> bool
        return os.path.exists(self._abs(fn))

    def size(self, fn):  # type: (str) -> int
        return os.stat(self._abs(fn)).st_size

    def isfile(self, fn):  # type: (str) -> bool
        return os.path.isfile(self._abs(fn))

    def isdir(self, fn):  # type: (str) -> bool
        return os.path.isdir(self._abs(fn))

    def listdir(self, fn):  # type: (str) -> List[str]
        return [
            abspath(urllib.parse.quote(str(l)), fn) for l in os.listdir(self._abs(fn))
        ]

    def join(self, path, *paths):  # type: (str, *str) -> str
        return os.path.join(path, *paths)

    def realpath(self, path):  # type: (str) -> str
        return os.path.realpath(path)

    # On windows os.path.realpath appends unecessary Drive, here we would avoid that
    def docker_compatible_realpath(self, path):  # type: (str) -> str
        if onWindows():
            if path.startswith("/"):
                return path
            return "/" + path
        return self.realpath(path)
