"""Abstracted IO access."""
from __future__ import absolute_import

import glob
import os
from io import open
from typing import IO, Any, List

from schema_salad.ref_resolver import file_uri, uri_file_path
from six.moves import urllib
from typing_extensions import Text
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .utils import onWindows


def abspath(src, basedir):  # type: (Text, Text) -> Text
    if src.startswith(u"file://"):
        abpath = Text(uri_file_path(str(src)))
    elif urllib.parse.urlsplit(src).scheme in ['http', 'https']:
        return src
    else:
        if basedir.startswith(u"file://"):
            abpath = src if os.path.isabs(src) else basedir+ '/'+ src
        else:
            abpath = src if os.path.isabs(src) else os.path.join(basedir, src)
    return abpath

class StdFsAccess(object):
    """Local filesystem implementation."""
    def __init__(self, basedir):  # type: (Text) -> None
        self.basedir = basedir

    def _abs(self, p):  # type: (Text) -> Text
        return abspath(p, self.basedir)

    def glob(self, pattern):  # type: (Text) -> List[Text]
        return [file_uri(str(self._abs(l))) for l in glob.glob(self._abs(pattern))]

    def open(self, fn, mode):  # type: (Text, str) -> IO[Any]
        return open(self._abs(fn), mode)

    def exists(self, fn):  # type: (Text) -> bool
        return os.path.exists(self._abs(fn))

    def size(self, fn):    # type: (Text) -> int
        return os.stat(self._abs(fn)).st_size

    def isfile(self, fn):  # type: (Text) -> bool
        return os.path.isfile(self._abs(fn))

    def isdir(self, fn):  # type: (Text) -> bool
        return os.path.isdir(self._abs(fn))

    def listdir(self, fn):  # type: (Text) -> List[Text]
        return [abspath(urllib.parse.quote(str(l)), fn) for l in os.listdir(self._abs(fn))]

    def join(self, path, *paths):  # type: (Text, *Text) -> Text
        return os.path.join(path, *paths)

    def realpath(self, path):  # type: (Text) -> Text
        return os.path.realpath(path)

    # On windows os.path.realpath appends unecessary Drive, here we would avoid that
    def docker_compatible_realpath(self, path):  # type: (Text) -> Text
        if onWindows():
            if path.startswith('/'):
                return path
            return '/'+path
        return self.realpath(path)
