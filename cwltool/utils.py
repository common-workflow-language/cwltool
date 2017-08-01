from __future__ import absolute_import

# no imports from cwltool allowed

import os
import shutil
import stat
import six
from six.moves import urllib
from six.moves import zip_longest
from typing import Any,Callable, Dict, List, Tuple, Text, Union

windows_default_container_id = "frolvlad/alpine-bash"

def aslist(l):  # type: (Any) -> List[Any]
    if isinstance(l, list):
        return l
    else:
        return [l]


def get_feature(self, feature):  # type: (Any, Any) -> Tuple[Any, bool]
    for t in reversed(self.requirements):
        if t["class"] == feature:
            return (t, True)
    for t in reversed(self.hints):
        if t["class"] == feature:
            return (t, False)
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
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if symlinks and os.path.islink(s):
            if os.path.lexists(d):
                os.remove(d)
            os.symlink(os.readlink(s), d)
            try:
                st = os.lstat(s)
                mode = stat.S_IMODE(st.st_mode)
                os.lchmod(d, mode)
            except:
                pass  # lchmod not available, only available on unix
        elif os.path.isdir(s):
            copytree_with_merge(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


# changes windowspath(only) appropriately to be passed to docker run command
# as docker treat them as unix paths so convert C:\Users\foo to /C/Users/foo
def docker_windows_path_adjust(path):
    # type: (Text) -> (Text)
    if path is not None and onWindows():
        sp=path.split(':')
        if len(sp)==2:
            sp[0]=sp[0].capitalize()  # Capitalizing windows Drive letters
            path=':'.join(sp)
        path = path.replace(':', '').replace('\\', '/')
        return path if path[0] == '/' else '/' + path
    return path


# changes docker path(only on windows os) appropriately back to Windows path
# so convert /C/Users/foo to C:\Users\foo
def docker_windows_reverse_path_adjust(path):
    # type: (Text) -> (Text)
    if path is not None and onWindows():
        if path[0] == '/':
            path=path[1:]
        else:
            raise ValueError("not a docker path")
        splitpath=path.split('/')
        splitpath[0]= splitpath[0]+':'
        return '\\'.join(splitpath)
    return path


# On docker in windows fileuri do not contain : in path
# To convert this file uri to windows compatible add : after drove letter,
# so file:///E/var becomes file:///E:/var
def docker_windows_reverse_fileuri_adjust(fileuri):
    # type: (Text) -> (Text)
    if fileuri is not None and onWindows():
        if urllib.parse.urlsplit(fileuri).scheme == "file":
            filesplit= fileuri.split("/")
            if filesplit[3][-1] != ':':
                filesplit[3]=filesplit[3]+':'
                return '/'.join(filesplit)
            else:
                return fileuri
        else:
            raise ValueError("not a file URI")
    return fileuri


# Check if we are on windows OS
def onWindows():
    # type: () -> (bool)
    return os.name == 'nt'



# On windows os.path.join would use backslash to join path, since we would use these paths in Docker we would convert it to /
def convert_pathsep_to_unix(path):  # type: (Text) -> (Text)
    if path is not None and onWindows():
        return path.replace('\\', '/')
    return path

# comparision function to be used in sorting
# python3 doesn't allow sorting of different
# types like str() and int().
# this function re-creates sorting nature in py2
# of heterogeneous list of `int` and `str`
def cmp_like_py2(dict1, dict2):  # type: (Dict[Text, Any], Dict[Text, Any]) -> int
    # extract lists from both dicts
    a, b = dict1["position"], dict2["position"]
    # iterate through both list till max of their size
    for i,j in zip_longest(a,b):
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


# util function to convert any present byte string
# to unicode string. input is a dict of nested dicts and lists
def bytes2str_in_dicts(a):
    # type: (Union[Dict[Text, Any], List[Any], Any]) -> Union[Text, List[Any], Dict[Text, Any]]

    # if input is dict, recursively call for each value
    if isinstance(a, dict):
        for k, v in dict.items(a):
            a[k] = bytes2str_in_dicts(v)
        return a

    # if list, iterate through list and fn call
    # for all its elements
    if isinstance(a, list):
        for idx, value in enumerate(a):
            a[idx] = bytes2str_in_dicts(value)
            return a

    # if value is bytes, return decoded string,
    elif isinstance(a, bytes):
        return a.decode('utf-8')

    # simply return elements itself
    return a
