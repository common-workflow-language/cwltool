from __future__ import absolute_import

# no imports from cwltool allowed

import os
import platform
import shutil
import stat
from typing import (Any, Callable, Dict, List, Optional, Text, Tuple, TypeVar,
                    Union)
from mypy_extensions import TypedDict

from pkg_resources import (Requirement, ResolutionError,  # type: ignore
                           resource_filename)

from six.moves import urllib, zip_longest

windows_default_container_id = "frolvlad/alpine-bash"

Directory = TypedDict('Directory',
                      {'class': Text, 'listing': List[Dict[Text, Text]],
                       'basename': Text})

DEFAULT_TMP_PREFIX = "tmp"

def aslist(l):  # type: (Any) -> List[Any]
    if isinstance(l, list):
        return l
    return [l]


def get_feature(self,    # type: Any
                feature  # type: Any
               ):  # type: (...) -> Tuple[Optional[Any], Optional[bool]]
    for item in reversed(self.requirements):
        if item["class"] == feature:
            return (item, True)
    for item in reversed(self.hints):
        if item["class"] == feature:
            return (item, False)
    return (None, None)


def copytree_with_merge(src, dst, symlinks=False, ignore=None):
    # type: (Text, Text, bool, Callable[..., Any]) -> None
    if not os.path.exists(dst):
        os.makedirs(dst)
        shutil.copystat(src, dst)
    lst = os.listdir(src)
    if ignore:
        excl = ignore(src, lst)
        lst = [x for x in lst if x not in excl]
    for item in lst:
        spath = os.path.join(src, item)
        dpath = os.path.join(dst, item)
        if symlinks and os.path.islink(spath):
            if os.path.lexists(dpath):
                os.remove(dpath)
            os.symlink(os.readlink(spath), dpath)
            try:
                s_stat = os.lstat(spath)
                mode = stat.S_IMODE(s_stat.st_mode)
                os.lchmod(dpath, mode)
            except:
                pass  # lchmod not available, only available on unix
        elif os.path.isdir(spath):
            copytree_with_merge(spath, dpath, symlinks, ignore)
        else:
            shutil.copy2(spath, dpath)

def docker_windows_path_adjust(path):
    # type: (Optional[Text]) -> Optional[Text]
    r"""
    Changes only windows paths so that the can be appropriately passed to the
    docker run command as as docker treats them as unix paths.

    Example: 'C:\Users\foo to /C/Users/foo (Docker for Windows) or /c/Users/foo
    (Docker toolbox).
    """
    if path is not None and onWindows():
        split = path.split(':')
        if len(split) == 2:
            if platform.win32_ver()[0] in ('7', '8'):  # type: ignore
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
    Change docker path (only on windows os) appropriately back to Window path/
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
        else:
            raise ValueError("not a file URI")
    return fileuri


def onWindows():
    # type: () -> (bool)
    """ Check if we are on Windows OS. """
    return os.name == 'nt'



def convert_pathsep_to_unix(path):  # type: (Text) -> (Text)
    """
    On windows os.path.join would use backslash to join path, since we would
    use these paths in Docker we would convert it to use forward slashes: /
    """
    if path is not None and onWindows():
        return path.replace('\\', '/')
    return path

def cmp_like_py2(dict1, dict2):  # type: (Dict[Text, Any], Dict[Text, Any]) -> int
    """
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


def bytes2str_in_dicts(inp  # type: Union[Dict[Text, Any], List[Any], Any]
                      ):  # type: (...) -> Union[Text, List[Any], Dict[Text, Any]]
    """
    Convert any present byte string to unicode string, inplace.
    input is a dict of nested dicts and lists
    """

    # if input is dict, recursively call for each value
    if isinstance(inp, dict):
        for k, val in dict.items(inp):
            inp[k] = bytes2str_in_dicts(val)
        return inp

    # if list, iterate through list and fn call
    # for all its elements
    if isinstance(inp, list):
        for idx, value in enumerate(inp):
            inp[idx] = bytes2str_in_dicts(value)
            return inp

    # if value is bytes, return decoded string,
    elif isinstance(inp, bytes):
        return inp.decode('utf-8')

    # simply return elements itself
    return inp
