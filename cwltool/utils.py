"""Shared functions and other definitions."""

import collections
import os
import platform
import random
import shutil
import stat
import string
import subprocess  # nosec
import sys
import tempfile
import urllib
import uuid
from functools import partial
from itertools import zip_longest
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from types import ModuleType
from typing import (
    IO,
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    MutableMapping,
    MutableSequence,
    NamedTuple,
    Optional,
    Set,
    Union,
    cast,
)

import pkg_resources
import requests
from cachecontrol import CacheControl
from cachecontrol.caches import FileCache
from mypy_extensions import TypedDict
from schema_salad.exceptions import ValidationException
from schema_salad.ref_resolver import Loader
from typing_extensions import TYPE_CHECKING, Deque

if TYPE_CHECKING:
    from .command_line_tool import CallbackJob, ExpressionJob
    from .job import CommandLineJob, JobBase
    from .stdfsaccess import StdFsAccess
    from .workflow_job import WorkflowJob

__random_outdir = None  # type: Optional[str]

CONTENT_LIMIT = 64 * 1024

windows_default_container_id = "frolvlad/alpine-bash"

DEFAULT_TMP_PREFIX = tempfile.gettempdir() + os.path.sep

processes_to_kill = collections.deque()  # type: Deque[subprocess.Popen[str]]

CWLOutputAtomType = Union[
    None,
    bool,
    str,
    int,
    float,
    MutableSequence[
        Union[
            None, bool, str, int, float, MutableSequence[Any], MutableMapping[str, Any]
        ]
    ],
    MutableMapping[
        str,
        Union[
            None, bool, str, int, float, MutableSequence[Any], MutableMapping[str, Any]
        ],
    ],
]
CWLOutputType = Union[
    bool,
    str,
    int,
    float,
    MutableSequence[CWLOutputAtomType],
    MutableMapping[str, CWLOutputAtomType],
]
CWLObjectType = MutableMapping[str, Optional[CWLOutputType]]
JobsType = Union[
    "CommandLineJob", "JobBase", "WorkflowJob", "ExpressionJob", "CallbackJob"
]
JobsGeneratorType = Generator[Optional[JobsType], None, None]
OutputCallbackType = Callable[[Optional[CWLObjectType], str], None]
ResolverType = Callable[["Loader", str], Optional[str]]
DestinationsType = MutableMapping[str, Optional[CWLOutputType]]
ScatterDestinationsType = MutableMapping[str, List[Optional[CWLOutputType]]]
ScatterOutputCallbackType = Callable[[Optional[ScatterDestinationsType], str], None]
SinkType = Union[CWLOutputType, CWLObjectType]
DirectoryType = TypedDict(
    "DirectoryType", {"class": str, "listing": List[CWLObjectType], "basename": str}
)
JSONAtomType = Union[Dict[str, Any], List[Any], str, int, float, bool, None]
JSONType = Union[
    Dict[str, JSONAtomType], List[JSONAtomType], str, int, float, bool, None
]
WorkflowStateItem = NamedTuple(
    "WorkflowStateItem",
    [
        ("parameter", CWLObjectType),
        ("value", Optional[CWLOutputType]),
        ("success", str),
    ],
)

ParametersType = List[CWLObjectType]
StepType = CWLObjectType  # WorkflowStep


def versionstring() -> str:
    """Version of CWLtool used to execute the workflow."""
    pkg = pkg_resources.require("cwltool")
    if pkg:
        return "%s %s" % (sys.argv[0], pkg[0].version)
    return "%s %s" % (sys.argv[0], "unknown version")


def aslist(thing: Any) -> MutableSequence[Any]:
    """Wrap any non-MutableSequence/list in a list."""
    if isinstance(thing, MutableSequence):
        return thing
    return [thing]


def copytree_with_merge(src: str, dst: str) -> None:
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


def docker_windows_path_adjust(path: str) -> str:
    r"""
    Adjust only windows paths for Docker.

    The docker run command treats them as unix paths.

    Example: 'C:\Users\foo to /C/Users/foo (Docker for Windows) or /c/Users/foo
    (Docker toolbox).
    """
    if onWindows():
        split = path.split(":")
        if len(split) == 2:
            if platform.win32_ver()[0] in ("7", "8"):
                # Docker toolbox uses lowecase windows Drive letters
                split[0] = split[0].lower()
            else:
                split[0] = split[0].capitalize()
                # Docker for Windows uses uppercase windows Drive letters
            path = ":".join(split)
        path = path.replace(":", "").replace("\\", "/")
        return path if path[0] == "/" else "/" + path
    return path


def docker_windows_reverse_path_adjust(path: str) -> str:
    r"""
    Change docker path (only on windows os) appropriately back to Windows path.

    Example:  /C/Users/foo to C:\Users\foo
    """
    if path is not None and onWindows():
        if path[0] == "/":
            path = path[1:]
        else:
            raise ValueError("not a docker path")
        splitpath = path.split("/")
        splitpath[0] = splitpath[0] + ":"
        return "\\".join(splitpath)
    return path


def docker_windows_reverse_fileuri_adjust(fileuri: str) -> str:
    r"""
    Convert fileuri to be MS Windows comptabile, if needed.

    On docker in windows fileuri do not contain : in path
    To convert this file uri to windows compatible add : after drive letter,
    so file:///E/var becomes file:///E:/var
    """
    if fileuri is not None and onWindows():
        if urllib.parse.urlsplit(fileuri).scheme == "file":
            filesplit = fileuri.split("/")
            if filesplit[3][-1] != ":":
                filesplit[3] = filesplit[3] + ":"
                return "/".join(filesplit)
            return fileuri
        raise ValueError("not a file URI")
    return fileuri


def onWindows() -> bool:
    """Check if we are on Windows OS."""
    return os.name == "nt"


def convert_pathsep_to_unix(path: str) -> str:
    """
    Convert path seperators to unix style.

    On windows os.path.join would use backslash to join path, since we would
    use these paths in Docker we would convert it to use forward slashes: /
    """
    if path is not None and onWindows():
        return path.replace("\\", "/")
    return path


def cmp_like_py2(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> int:
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


def bytes2str_in_dicts(
    inp: Union[MutableMapping[str, Any], MutableSequence[Any], Any],
):
    # type: (...) -> Union[str, MutableSequence[Any], MutableMapping[str, Any]]
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
        return inp.decode("utf-8")

    # simply return elements itself
    return inp


def visit_class(rec: Any, cls: Iterable[Any], op: Callable[..., Any]) -> None:
    """Apply a function to with "class" in cls."""
    if isinstance(rec, MutableMapping):
        if "class" in rec and rec.get("class") in cls:
            op(rec)
        for d in rec:
            visit_class(rec[d], cls, op)
    if isinstance(rec, MutableSequence):
        for d in rec:
            visit_class(d, cls, op)


def visit_field(rec: Any, field: str, op: Callable[..., Any]) -> None:
    """Apply a function to mapping with 'field'."""
    if isinstance(rec, MutableMapping):
        if field in rec:
            rec[field] = op(rec[field])
        for d in rec:
            visit_field(rec[d], field, op)
    if isinstance(rec, MutableSequence):
        for d in rec:
            visit_field(d, field, op)


def random_outdir() -> str:
    """Return the random directory name chosen to use for tool / workflow output."""
    global __random_outdir
    if not __random_outdir:
        __random_outdir = "/" + "".join(
            [random.choice(string.ascii_letters) for _ in range(6)]  # nosec
        )
        return __random_outdir
    return __random_outdir


#
# Simple multi-platform (fcntl/msvrt) file locking wrapper
#
fcntl = None  # type: Optional[ModuleType]
msvcrt = None  # type: Optional[ModuleType]
try:
    import fcntl  # type: ignore
except ImportError:
    import msvcrt  # type: ignore


def shared_file_lock(fd: IO[Any]) -> None:
    if fcntl:
        fcntl.flock(fd.fileno(), fcntl.LOCK_SH)  # type: ignore
    elif msvcrt:
        msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1024)  # type: ignore


def upgrade_lock(fd: IO[Any]) -> None:
    if fcntl:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)  # type: ignore
    elif msvcrt:
        pass


def adjustFileObjs(
    rec, op
):  # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply an update function to each File object in the object `rec`."""
    visit_class(rec, ("File",), op)


def adjustDirObjs(rec, op):
    # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply an update function to each Directory object in the object `rec`."""
    visit_class(rec, ("Directory",), op)


def dedup(listing: List[CWLObjectType]) -> List[CWLObjectType]:
    marksub = set()

    def mark(d: Dict[str, str]) -> None:
        marksub.add(d["location"])

    for entry in listing:
        if entry["class"] == "Directory":
            for e in cast(List[CWLObjectType], entry.get("listing", [])):
                adjustFileObjs(e, mark)
                adjustDirObjs(e, mark)

    dd = []
    markdup = set()  # type: Set[str]
    for r in listing:
        if r["location"] not in marksub and r["location"] not in markdup:
            dd.append(r)
            markdup.add(cast(str, r["location"]))

    return dd


def get_listing(
    fs_access: "StdFsAccess", rec: CWLObjectType, recursive: bool = True
) -> None:
    if rec.get("class") != "Directory":
        finddirs = []  # type: List[CWLObjectType]
        visit_class(rec, ("Directory",), finddirs.append)
        for f in finddirs:
            get_listing(fs_access, f, recursive=recursive)
        return
    if "listing" in rec:
        return
    listing = []  # type: List[CWLOutputAtomType]
    loc = cast(str, rec["location"])
    for ld in fs_access.listdir(loc):
        parse = urllib.parse.urlparse(ld)
        bn = os.path.basename(urllib.request.url2pathname(parse.path))
        if fs_access.isdir(ld):
            ent = {
                "class": "Directory",
                "location": ld,
                "basename": bn,
            }  # type: MutableMapping[str, Any]
            if recursive:
                get_listing(fs_access, ent, recursive)
            listing.append(ent)
        else:
            listing.append({"class": "File", "location": ld, "basename": bn})
    rec["listing"] = listing


def trim_listing(obj):  # type: (Dict[str, Any]) -> None
    """
    Remove 'listing' field from Directory objects that are file references.

    It redundant and potentially expensive to pass fully enumerated Directory
    objects around if not explicitly needed, so delete the 'listing' field when
    it is safe to do so.
    """
    if obj.get("location", "").startswith("file://") and "listing" in obj:
        del obj["listing"]


def downloadHttpFile(httpurl):
    # type: (str) -> str
    cache_session = None
    if "XDG_CACHE_HOME" in os.environ:
        directory = os.environ["XDG_CACHE_HOME"]
    elif "HOME" in os.environ:
        directory = os.environ["HOME"]
    else:
        directory = os.path.expanduser("~")

    cache_session = CacheControl(
        requests.Session(),
        cache=FileCache(os.path.join(directory, ".cache", "cwltool")),
    )

    r = cache_session.get(httpurl, stream=True)
    with NamedTemporaryFile(mode="wb", delete=False) as f:
        for chunk in r.iter_content(chunk_size=16384):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
    r.close()
    return str(f.name)


def ensure_writable(path):  # type: (str) -> None
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for name in files:
                j = os.path.join(root, name)
                st = os.stat(j)
                mode = stat.S_IMODE(st.st_mode)
                os.chmod(j, mode | stat.S_IWUSR)
            for name in dirs:
                j = os.path.join(root, name)
                st = os.stat(j)
                mode = stat.S_IMODE(st.st_mode)
                os.chmod(j, mode | stat.S_IWUSR)
    else:
        st = os.stat(path)
        mode = stat.S_IMODE(st.st_mode)
        os.chmod(path, mode | stat.S_IWUSR)


def ensure_non_writable(path):  # type: (str) -> None
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for name in files:
                j = os.path.join(root, name)
                st = os.stat(j)
                mode = stat.S_IMODE(st.st_mode)
                os.chmod(j, mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
            for name in dirs:
                j = os.path.join(root, name)
                st = os.stat(j)
                mode = stat.S_IMODE(st.st_mode)
                os.chmod(j, mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    else:
        st = os.stat(path)
        mode = stat.S_IMODE(st.st_mode)
        os.chmod(path, mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)


def normalizeFilesDirs(
    job: Optional[
        Union[
            MutableSequence[MutableMapping[str, Any]],
            MutableMapping[str, Any],
            DirectoryType,
        ]
    ]
) -> None:
    def addLocation(d):  # type: (Dict[str, Any]) -> None
        if "location" not in d:
            if d["class"] == "File" and ("contents" not in d):
                raise ValidationException(
                    "Anonymous file object must have 'contents' and 'basename' fields."
                )
            if d["class"] == "Directory" and (
                "listing" not in d or "basename" not in d
            ):
                raise ValidationException(
                    "Anonymous directory object must have 'listing' and 'basename' fields."
                )
            d["location"] = "_:" + str(uuid.uuid4())
            if "basename" not in d:
                d["basename"] = d["location"][2:]

        parse = urllib.parse.urlparse(d["location"])
        path = parse.path
        # strip trailing slash
        if path.endswith("/"):
            if d["class"] != "Directory":
                raise ValidationException(
                    "location '%s' ends with '/' but is not a Directory" % d["location"]
                )
            path = path.rstrip("/")
            d["location"] = urllib.parse.urlunparse(
                (
                    parse.scheme,
                    parse.netloc,
                    path,
                    parse.params,
                    parse.query,
                    parse.fragment,
                )
            )

        if not d.get("basename"):
            if path.startswith("_:"):
                d["basename"] = str(path[2:])
            else:
                d["basename"] = str(os.path.basename(urllib.request.url2pathname(path)))

        if d["class"] == "File":
            nr, ne = os.path.splitext(d["basename"])
            if d.get("nameroot") != nr:
                d["nameroot"] = str(nr)
            if d.get("nameext") != ne:
                d["nameext"] = str(ne)

    visit_class(job, ("File", "Directory"), addLocation)


def posix_path(local_path: str) -> str:
    return str(PurePosixPath(Path(local_path)))


def local_path(posix_path: str) -> str:
    return str(Path(posix_path))


def create_tmp_dir(tmpdir_prefix: str) -> str:
    """Create a temporary directory that respects the given tmpdir_prefix."""
    tmp_dir, tmp_prefix = os.path.split(tmpdir_prefix)
    return tempfile.mkdtemp(prefix=tmp_prefix, dir=tmp_dir)
