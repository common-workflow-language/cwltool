from __future__ import absolute_import
import collections
import logging
import os
import stat
import uuid
from functools import partial
from tempfile import NamedTemporaryFile

import requests
from cachecontrol import CacheControl
from cachecontrol.caches import FileCache
from typing import Any, Callable, Dict, Iterable, List, Set, Text, Tuple, Union, MutableMapping

import schema_salad.validate as validate
from schema_salad.ref_resolver import uri_file_path
from schema_salad.sourceline import SourceLine
from six.moves import urllib

from .utils import convert_pathsep_to_unix

from .stdfsaccess import StdFsAccess, abspath

_logger = logging.getLogger("cwltool")

MapperEnt = collections.namedtuple("MapperEnt", ["resolved", "target", "type", "staged"])


def adjustFiles(rec, op):  # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply a mapping function to each File path in the object `rec`."""

    if isinstance(rec, dict):
        if rec.get("class") == "File":
            rec["path"] = op(rec["path"])
        for d in rec:
            adjustFiles(rec[d], op)
    if isinstance(rec, list):
        for d in rec:
            adjustFiles(d, op)

def visit_class(rec, cls, op):  # type: (Any, Iterable, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply a function to with "class" in cls."""

    if isinstance(rec, dict):
        if "class" in rec and rec.get("class") in cls:
            op(rec)
        for d in rec:
            visit_class(rec[d], cls, op)
    if isinstance(rec, list):
        for d in rec:
            visit_class(d, cls, op)

def adjustFileObjs(rec, op):  # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply an update function to each File object in the object `rec`."""
    visit_class(rec, ("File",), op)

def adjustDirObjs(rec, op):
    # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply an update function to each Directory object in the object `rec`."""
    visit_class(rec, ("Directory",), op)

def normalizeFilesDirs(job):
    # type: (Union[List[Dict[Text, Any]], MutableMapping[Text, Any]]) -> None
    def addLocation(d):
        if "location" not in d:
            if d["class"] == "File" and ("contents" not in d):
                raise validate.ValidationException("Anonymous file object must have 'contents' and 'basename' fields.")
            if d["class"] == "Directory" and ("listing" not in d or "basename" not in d):
                raise validate.ValidationException(
                    "Anonymous directory object must have 'listing' and 'basename' fields.")
            d["location"] = "_:" + Text(uuid.uuid4())
            if "basename" not in d:
                d["basename"] = d["location"][2:]

        parse = urllib.parse.urlparse(d["location"])
        path = parse.path
        # strip trailing slash
        if path.endswith("/"):
            if d["class"] != "Directory":
                raise validate.ValidationException(
                    "location '%s' ends with '/' but is not a Directory" % d["location"])
            path = path.rstrip("/")
            d["location"] = urllib.parse.urlunparse((parse.scheme, parse.netloc, path, parse.params, parse.query, parse.fragment))

        if "basename" not in d:
            d["basename"] = os.path.basename(urllib.request.url2pathname(path))

        if d["class"] == "File":
            d["nameroot"], d["nameext"] = os.path.splitext(d["basename"])

    visit_class(job, ("File", "Directory"), addLocation)


def dedup(listing):  # type: (List[Any]) -> List[Any]
    marksub = set()

    def mark(d):
        marksub.add(d["location"])

    for l in listing:
        if l["class"] == "Directory":
            for e in l.get("listing", []):
                adjustFileObjs(e, mark)
                adjustDirObjs(e, mark)

    dd = []
    markdup = set()  # type: Set[Text]
    for r in listing:
        if r["location"] not in marksub and r["location"] not in markdup:
            dd.append(r)
            markdup.add(r["location"])

    return dd

def get_listing(fs_access, rec, recursive=True):
    # type: (StdFsAccess, Dict[Text, Any], bool) -> None
    if "listing" in rec:
        return
    listing = []
    loc = rec["location"]
    for ld in fs_access.listdir(loc):
        parse = urllib.parse.urlparse(ld)
        bn = os.path.basename(urllib.request.url2pathname(parse.path))
        if fs_access.isdir(ld):
            ent = {u"class": u"Directory",
                   u"location": ld,
                   u"basename": bn}
            if recursive:
                get_listing(fs_access, ent, recursive)
            listing.append(ent)
        else:
            listing.append({"class": "File", "location": ld, "basename": bn})
    rec["listing"] = listing

def trim_listing(obj):
    """Remove 'listing' field from Directory objects that are file references.

    It redundant and potentially expensive to pass fully enumerated Directory
    objects around if not explicitly needed, so delete the 'listing' field when
    it is safe to do so.

    """

    if obj.get("location", "").startswith("file://") and "listing" in obj:
        del obj["listing"]

# Download http Files
def downloadHttpFile(httpurl):
    # type: (Text) -> Text
    cache_session = None
    if "XDG_CACHE_HOME" in os.environ:
        directory = os.environ["XDG_CACHE_HOME"]
    elif "HOME" in os.environ:
        directory = os.environ["HOME"]
    else:
        directory = os.path.expanduser('~')

    cache_session = CacheControl(
        requests.Session(),
        cache=FileCache(
            os.path.join(directory, ".cache", "cwltool")))

    r = cache_session.get(httpurl, stream=True)
    with NamedTemporaryFile(mode='wb', delete=False) as f:
        for chunk in r.iter_content(chunk_size=16384):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
    r.close()
    return f.name

def ensure_writable(path):
    # type: (Text) -> None
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for name in files:
                j = os.path.join(root, name)
                st = os.stat(j)
                mode = stat.S_IMODE(st.st_mode)
                os.chmod(j, mode|stat.S_IWUSR)
            for name in dirs:
                j = os.path.join(root, name)
                st = os.stat(j)
                mode = stat.S_IMODE(st.st_mode)
                os.chmod(j, mode|stat.S_IWUSR)
    else:
        st = os.stat(path)
        mode = stat.S_IMODE(st.st_mode)
        os.chmod(path, mode|stat.S_IWUSR)

class PathMapper(object):
    """Mapping of files from relative path provided in the file to a tuple of
    (absolute local path, absolute container path)

    The tao of PathMapper:

    The initializer takes a list of File and Directory objects, a base
    directory (for resolving relative references) and a staging directory
    (where the files are mapped to).

    The purpose of the setup method is to determine where each File or
    Directory should be placed on the target file system (relative to
    stagedir).

    If separatedirs=True, unrelated files will be isolated in their own
    directories under stagedir. If separatedirs=False, files and directories
    will all be placed in stagedir (with the possibility for name
    collisions...)

    The path map maps the "location" of the input Files and Directory objects
    to a tuple (resolved, target, type). The "resolved" field is the "real"
    path on the local file system (after resolving relative paths and
    traversing symlinks). The "target" is the path on the target file system
    (under stagedir). The type is the object type (one of File, Directory,
    CreateFile, WritableFile).

    The latter two (CreateFile, WritableFile) are used by
    InitialWorkDirRequirement to indicate files that are generated on the fly
    (CreateFile, in this case "resolved" holds the file contents instead of the
    path because they file doesn't exist) or copied into the output directory
    so they can be opened for update ("r+" or "a") (WritableFile).

    """

    def __init__(self, referenced_files, basedir, stagedir, separateDirs=True):
        # type: (List[Any], Text, Text, bool) -> None
        self._pathmap = {}  # type: Dict[Text, MapperEnt]
        self.stagedir = stagedir
        self.separateDirs = separateDirs
        self.setup(dedup(referenced_files), basedir)

    def visitlisting(self, listing, stagedir, basedir, copy=False, staged=False):
        # type: (List[Dict[Text, Any]], Text, Text, bool, bool) -> None
        for ld in listing:
            self.visit(ld, stagedir, basedir, copy=ld.get("writable", copy), staged=staged)

    def visit(self, obj, stagedir, basedir, copy=False, staged=False):
        # type: (Dict[Text, Any], Text, Text, bool, bool) -> None
        tgt = convert_pathsep_to_unix(
            os.path.join(stagedir, obj["basename"]))
        if obj["location"] in self._pathmap:
            return
        if obj["class"] == "Directory":
            if obj["location"].startswith("file://"):
                resolved = uri_file_path(obj["location"])
            else:
                resolved = obj["location"]
            self._pathmap[obj["location"]] = MapperEnt(resolved, tgt, "WritableDirectory" if copy else "Directory", staged)
            if obj["location"].startswith("file://"):
                staged = False
            self.visitlisting(obj.get("listing", []), tgt, basedir, copy=copy, staged=staged)
        elif obj["class"] == "File":
            path = obj["location"]
            ab = abspath(path, basedir)
            if "contents" in obj and obj["location"].startswith("_:"):
                self._pathmap[obj["location"]] = MapperEnt(obj["contents"], tgt, "CreateFile", staged)
            else:
                with SourceLine(obj, "location", validate.ValidationException, _logger.isEnabledFor(logging.DEBUG)):
                    deref = ab
                    if urllib.parse.urlsplit(deref).scheme in ['http','https']:
                        deref = downloadHttpFile(path)
                    else:
                        # Dereference symbolic links
                        st = os.lstat(deref)
                        while stat.S_ISLNK(st.st_mode):
                            rl = os.readlink(deref)
                            deref = rl if os.path.isabs(rl) else os.path.join(
                                os.path.dirname(deref), rl)
                            st = os.lstat(deref)

                    self._pathmap[path] = MapperEnt(deref, tgt, "WritableFile" if copy else "File", staged)
                    self.visitlisting(obj.get("secondaryFiles", []), stagedir, basedir, copy=copy, staged=staged)

    def setup(self, referenced_files, basedir):
        # type: (List[Any], Text) -> None

        # Go through each file and set the target to its own directory along
        # with any secondary files.
        stagedir = self.stagedir
        for fob in referenced_files:
            if self.separateDirs:
                stagedir = os.path.join(self.stagedir, "stg%s" % uuid.uuid4())
            self.visit(fob, stagedir, basedir, copy=fob.get("writable"), staged=True)

    def mapper(self, src):  # type: (Text) -> MapperEnt
        if u"#" in src:
            i = src.index(u"#")
            p = self._pathmap[src[:i]]
            return MapperEnt(p.resolved, p.target + src[i:], p.type, p.staged)
        else:
            return self._pathmap[src]

    def files(self):  # type: () -> List[Text]
        return list(self._pathmap.keys())

    def items(self):  # type: () -> List[Tuple[Text, MapperEnt]]
        return list(self._pathmap.items())

    def reversemap(self, target):  # type: (Text) -> Tuple[Text, Text]
        for k, v in self._pathmap.items():
            if v[1] == target:
                return (k, v[0])
        return None

    def update(self, key, resolved, target, type, stage):  # type: (Text, Text, Text, Text, bool) -> None
        self._pathmap[key] = MapperEnt(resolved, target, type, stage)

    def __contains__(self, key):
        return key in self._pathmap
