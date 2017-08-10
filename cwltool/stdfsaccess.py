from __future__ import absolute_import
import glob
import os
from io import open
from typing import BinaryIO, List, Union, Text, IO, overload

from .utils import onWindows

import six
from six.moves import urllib
from schema_salad.ref_resolver import file_uri, uri_file_path

def abspath(src, basedir):  # type: (Text, Text) -> Text
    if src.startswith(u"file://"):
        ab = six.text_type(uri_file_path(str(src)))
    elif urllib.parse.urlsplit(src).scheme in ['http','https']:
        return src
    else:
        if basedir.startswith(u"file://"):
            ab = src if os.path.isabs(src) else basedir+ '/'+ src
        else:
            ab = src if os.path.isabs(src) else os.path.join(basedir, src)
    return ab

class StdFsAccess(object):
    def __init__(self, basedir):  # type: (Text) -> None
        self.basedir = basedir

    def _abs(self, p):  # type: (Text) -> Text
        return abspath(p, self.basedir)

    def glob(self, pattern):  # type: (Text) -> List[Text]
        return [file_uri(str(self._abs(l))) for l in glob.glob(self._abs(pattern))]

    # overload is related to mypy type checking and in no way
    # modifies the behaviour of the function.
    @overload
    def open(self, fn, mode='rb'):  # type: (Text, str) -> IO[bytes]
        pass

    @overload
    def open(self, fn, mode='r'):  # type: (Text, str) -> IO[str]
        pass

    def open(self, fn, mode):
        return open(self._abs(fn), mode)

    def exists(self, fn):  # type: (Text) -> bool
        return os.path.exists(self._abs(fn))

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
