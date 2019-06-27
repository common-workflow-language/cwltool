"""Shared functions and other definitions."""
from __future__ import absolute_import

import collections
import os
import platform
import random
import shutil
import string
import sys
import tempfile
from functools import partial  # pylint: disable=unused-import
from typing import (IO, Any, AnyStr, Callable,  # pylint: disable=unused-import
                    Dict, Iterable, List, MutableMapping, MutableSequence,
                    Optional, Union)

import pkg_resources
from mypy_extensions import TypedDict
from schema_salad.utils import json_dump, json_dumps  # pylint: disable=unused-import
from six.moves import urllib, zip_longest
from typing_extensions import Deque, Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from pathlib2 import Path

# no imports from cwltool allowed
if os.name == 'posix':
    if sys.version_info < (3, 5):
        import subprocess32 as subprocess  # nosec # pylint: disable=unused-import
    else:
        import subprocess  # nosec # pylint: disable=unused-import
else:
    import subprocess  # type: ignore  # nosec

windows_default_container_id = "frolvlad/alpine-bash"

Directory = TypedDict('Directory',
                      {'class': Text, 'listing': List[Dict[Text, Text]],
                       'basename': Text})

DEFAULT_TMP_PREFIX = tempfile.gettempdir() + os.path.sep

processes_to_kill = collections.deque()  # type: Deque[subprocess.Popen]

def versionstring():
    # type: () -> Text
    """Version of CWLtool used to execute the workflow."""
    pkg = pkg_resources.require("cwltool")
    if pkg:
        return u"%s %s" % (sys.argv[0], pkg[0].version)
    return u"%s %s" % (sys.argv[0], "unknown version")

def aslist(l):  # type: (Any) -> MutableSequence[Any]
    """Wrap any non-MutableSequence/list in a list."""
    if isinstance(l, MutableSequence):
        return l
    return [l]

def copytree_with_merge(src, dst):  # type: (Text, Text) -> None
    if not os.path.exists(dst):
        os.makedirs(dst)
        shutil.copystat(src, dst)
    lst = os.listdir(src)
    for item in lst:
        spath = os.path.join(src, item)
        dpath = os.path.join(dst, item)
        if os.path.isdir(spath):
            copytree_with_merge(spath, dpath)
        else:
            shutil.copy2(spath, dpath)

def docker_windows_path_adjust(path):
    # type: (Text) -> Text
    r"""
    Adjust only windows paths for Docker.

    The docker run command treats them as unix paths.

    Example: 'C:\Users\foo to /C/Users/foo (Docker for Windows) or /c/Users/foo
    (Docker toolbox).
    """
    if onWindows():
        split = path.split(':')
        if len(split) == 2:
            if platform.win32_ver()[0] in ('7', '8'):
                split[0] = split[0].lower()  # Docker toolbox uses lowecase windows Drive letters
            else:
                split[0] = split[0].capitalize()
                # Docker for Windows uses uppercase windows Drive letters
            path = ':'.join(split)
        path = path.replace(':', '').replace('\\', '/')
        return path if path[0] == '/' else '/' + path
    return path


def docker_windows_reverse_path_adjust(path):
    # type: (Text) -> (Text)
    r"""
    Change docker path (only on windows os) appropriately back to Windows path.

    Example:  /C/Users/foo to C:\Users\foo
    """
    if path is not None and onWindows():
        if path[0] == '/':
            path = path[1:]
        else:
            raise ValueError("not a docker path")
        splitpath = path.split('/')
        splitpath[0] = splitpath[0]+':'
        return '\\'.join(splitpath)
    return path


def docker_windows_reverse_fileuri_adjust(fileuri):
    # type: (Text) -> (Text)
    r"""
    Convert fileuri to be MS Windows comptabile, if needed.

    On docker in windows fileuri do not contain : in path
    To convert this file uri to windows compatible add : after drive letter,
    so file:///E/var becomes file:///E:/var
    """
    if fileuri is not None and onWindows():
        if urllib.parse.urlsplit(fileuri).scheme == "file":
            filesplit = fileuri.split("/")
            if filesplit[3][-1] != ':':
                filesplit[3] = filesplit[3]+':'
                return '/'.join(filesplit)
            return fileuri
        raise ValueError("not a file URI")
    return fileuri


def onWindows():
    # type: () -> (bool)
    """Check if we are on Windows OS."""
    return os.name == 'nt'


def convert_pathsep_to_unix(path):  # type: (Text) -> (Text)
    """
    Convert path seperators to unix style.

    On windows os.path.join would use backslash to join path, since we would
    use these paths in Docker we would convert it to use forward slashes: /
    """
    if path is not None and onWindows():
        return path.replace('\\', '/')
    return path

def cmp_like_py2(dict1, dict2):  # type: (Dict[Text, Any], Dict[Text, Any]) -> int
    """
    Compare in the same manner as Python2.

    Comparision function to be used in sorting as python3 doesn't allow sorting
    of different types like str() and int().
    This function re-creates sorting nature in py2 of heterogeneous list of
    `int` and `str`
    """
    # extract lists from both dicts
    first, second = dict1["position"], dict2["position"]
    # iterate through both list till max of their size
    for i, j in zip_longest(first, second):
        if i == j:
            continue
        # in case 1st list is smaller
        # should come first in sorting
        if i is None:
            return -1
        # if 1st list is longer,
        # it should come later in sort
        elif j is None:
            return 1

        # if either of the list contains str element
        # at any index, both should be str before comparing
        if isinstance(i, str) or isinstance(j, str):
            return 1 if str(i) > str(j) else -1
        # int comparison otherwise
        return 1 if i > j else -1
    # if both lists are equal
    return 0


def bytes2str_in_dicts(inp  # type: Union[MutableMapping[Text, Any], MutableSequence[Any], Any]
                      ):
    # type: (...) -> Union[Text, MutableSequence[Any], MutableMapping[Text, Any]]
    """
    Convert any present byte string to unicode string, inplace.

    input is a dict of nested dicts and lists
    """
    # if input is dict, recursively call for each value
    if isinstance(inp, MutableMapping):
        for k in inp:
            inp[k] = bytes2str_in_dicts(inp[k])
        return inp

    # if list, iterate through list and fn call
    # for all its elements
    if isinstance(inp, MutableSequence):
        for idx, value in enumerate(inp):
            inp[idx] = bytes2str_in_dicts(value)
            return inp

    # if value is bytes, return decoded string,
    elif isinstance(inp, bytes):
        return inp.decode('utf-8')

    # simply return elements itself
    return inp


def visit_class(rec, cls, op):
    # type: (Union[MutableMapping[Text, Text], MutableSequence[MutableMapping[Text, Text]], Any], Iterable[Text], Union[Callable[..., Any], partial[Any]]) -> None
    """Apply a function to with "class" in cls."""
    if isinstance(rec, MutableMapping):
        if "class" in rec and rec.get("class") in cls:
            op(rec)
        for d in rec:
            visit_class(rec[d], cls, op)
    if isinstance(rec, MutableSequence):
        for d in rec:
            visit_class(d, cls, op)

def visit_field(rec, field, op):
    # type: (Any, Text, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply a function to mapping with 'field'."""
    if isinstance(rec, MutableMapping):
        if field in rec:
            rec[field] = op(rec[field])
        for d in rec:
            visit_field(rec[d], field, op)
    if isinstance(rec, MutableSequence):
        for d in rec:
            visit_field(d, field, op)


def random_outdir():  # type: () -> Text
    """Return the random directory name chosen to use for tool / workflow output."""
    # compute this once and store it as a function attribute - each subsequent call will return the same value
    if not hasattr(random_outdir, 'outdir'):
        random_outdir.outdir = '/' + ''.join([random.choice(string.ascii_letters) for _ in range(6)])  # type: ignore  # nosec
    return random_outdir.outdir  # type: ignore

#
# Simple multi-platform (fcntl/msvrt) file locking wrapper
#
try:
    import fcntl

    def shared_file_lock(fd):  # type: (IO[Any]) -> None
        fcntl.flock(fd.fileno(), fcntl.LOCK_SH)

    def upgrade_lock(fd):  # type: (IO[Any]) -> None
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)

except ImportError:
    import msvcrt

    def shared_file_lock(fd):  # type: (IO[Any]) -> None
        msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1024)  # type: ignore

    def upgrade_lock(fd):  # type: (IO[Any]) -> None
        pass
