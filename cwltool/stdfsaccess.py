"""Abstracted IO access."""

import glob
import os
import urllib
import abc
from typing import IO, Any, List

from mypy_extensions import mypyc_attr
from schema_salad.ref_resolver import file_uri, uri_file_path


def abspath(src: str, basedir: str) -> str:
    if src.startswith("file://"):
        abpath = uri_file_path(src)
    elif urllib.parse.urlsplit(src).scheme in ["http", "https"]:
        return src
    else:
        if basedir.startswith("file://"):
            abpath = src if os.path.isabs(src) else basedir + "/" + src
        else:
            abpath = src if os.path.isabs(src) else os.path.join(basedir, src)
    return abpath


@mypyc_attr(allow_interpreted_subclasses=True)
class StdFsAccess(metaclass=abc.ABCMeta):
    """Abstract base for filesystem implementation."""

    @abc.abstractmethod
    def glob(self, pattern: str) -> List[str]:
        pass

    @abc.abstractmethod
    def open(self, fn: str, mode: str) -> IO[Any]:
        pass

    @abc.abstractmethod
    def exists(self, fn: str) -> bool:
        pass

    @abc.abstractmethod
    def size(self, fn: str) -> int:
        pass

    @abc.abstractmethod
    def isfile(self, fn: str) -> bool:
        pass

    @abc.abstractmethod
    def isdir(self, fn: str) -> bool:
        pass

    @abc.abstractmethod
    def listdir(self, fn: str) -> List[str]:
        pass

    @abc.abstractmethod
    def join(self, path, *paths):  # type: (str, *str) -> str
        pass

    @abc.abstractmethod
    def realpath(self, path: str) -> str:
        pass


class LocalFsAccess(StdFsAccess):
    """Local filesystem implementation."""

    def __init__(self, basedir: str) -> None:
        """Perform operations with respect to a base directory."""
        self.basedir = basedir

    def _abs(self, p: str) -> str:
        return abspath(p, self.basedir)

    def glob(self, pattern: str) -> List[str]:
        return [
            file_uri(str(self._abs(line))) for line in glob.glob(self._abs(pattern))
        ]

    def open(self, fn: str, mode: str) -> IO[Any]:
        return open(self._abs(fn), mode)

    def exists(self, fn: str) -> bool:
        return os.path.exists(self._abs(fn))

    def size(self, fn: str) -> int:
        return os.stat(self._abs(fn)).st_size

    def isfile(self, fn: str) -> bool:
        return os.path.isfile(self._abs(fn))

    def isdir(self, fn: str) -> bool:
        return os.path.isdir(self._abs(fn))

    def listdir(self, fn: str) -> List[str]:
        return [
            abspath(urllib.parse.quote(entry), fn)
            for entry in os.listdir(self._abs(fn))
        ]

    def join(self, path, *paths):  # type: (str, *str) -> str
        return os.path.join(path, *paths)

    def realpath(self, path: str) -> str:
        return os.path.realpath(path)
