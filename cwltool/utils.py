# no imports from cwltool allowed
import os
import shutil
import stat
from typing import (Any, Callable, List, Text, Tuple)
import six
from six.moves import urllib


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
            if "requirement" in t and t["requirement"] is True:
                return(t, True)
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
                os.lchmod(d, mode)  # type: ignore
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
    if path is not None and os.name == 'nt':
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
    if path is not None and os.name == 'nt':
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
    if fileuri is not None and os.name == 'nt':
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
