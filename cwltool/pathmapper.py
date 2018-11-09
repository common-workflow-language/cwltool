from __future__ import absolute_import

import collections
import logging
import os
import stat
import uuid
from functools import partial  # pylint: disable=unused-import
from tempfile import NamedTemporaryFile
from typing import (Any, Callable, Dict, List, MutableMapping, MutableSequence,
                    Optional, Set, Tuple, Union)

import requests
from cachecontrol import CacheControl
from cachecontrol.caches import FileCache
from schema_salad import validate
from schema_salad.ref_resolver import uri_file_path
from schema_salad.sourceline import SourceLine
from six.moves import urllib
from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .loghandler import _logger
from .stdfsaccess import StdFsAccess, abspath  # pylint: disable=unused-import
from .utils import Directory  # pylint: disable=unused-import
from .utils import convert_pathsep_to_unix, visit_class


MapperEnt = collections.namedtuple("MapperEnt", ["resolved", "target", "type", "staged"])


def adjustFiles(rec, op):  # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply a mapping function to each File path in the object `rec`."""

    if isinstance(rec, MutableMapping):
        if rec.get("class") == "File":
            rec["path"] = op(rec["path"])
        for d in rec:
            adjustFiles(rec[d], op)
    if isinstance(rec, MutableSequence):
        for d in rec:
            adjustFiles(d, op)


def adjustFileObjs(rec, op):  # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply an update function to each File object in the object `rec`."""
    visit_class(rec, ("File",), op)

def adjustDirObjs(rec, op):
    # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply an update function to each Directory object in the object `rec`."""
    visit_class(rec, ("Directory",), op)

def normalizeFilesDirs(job):
    # type: (Optional[Union[List[Dict[Text, Any]], MutableMapping[Text, Any], Directory]]) -> None
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
    # type: (StdFsAccess, MutableMapping[Text, Any], bool) -> None
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

def ensure_writable(path):  # type: (Text) -> None
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

def ensure_non_writable(path):  # type: (Text) -> None
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for name in files:
                j = os.path.join(root, name)
                st = os.stat(j)
                mode = stat.S_IMODE(st.st_mode)
                os.chmod(j,
                         mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
            for name in dirs:
                j = os.path.join(root, name)
                st = os.stat(j)
                mode = stat.S_IMODE(st.st_mode)
                os.chmod(j,
                         mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    else:
        st = os.stat(path)
        mode = stat.S_IMODE(st.st_mode)
        os.chmod(path, mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)

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
    CreateFile, WritableFile, CreateWritableFile).

    The latter three (CreateFile, WritableFile, CreateWritableFile) are used by
    InitialWorkDirRequirement to indicate files that are generated on the fly
    (CreateFile and CreateWritableFile, in this case "resolved" holds the file
    contents instead of the path because they file doesn't exist) or copied
    into the output directory so they can be opened for update ("r+" or "a")
    (WritableFile and CreateWritableFile).

    """

    def __init__(self, referenced_files, basedir, stagedir, separateDirs=True):
        # type: (List[Any], Text, Text, bool) -> None
        self._pathmap = {}  # type: Dict[Text, MapperEnt]
        self._setup_pathmap(dedup(referenced_files), basedir, stagedir, separateDirs)

    def visitlisting(self, listing, stagedir, basedir, copy=False, staged=False):
        # type: (List[Dict[Text, Any]], Text, Text, bool, bool) -> None
        for entry in listing:
            copy = entry.get("writable", copy)
            self.visit(entry, stagedir, basedir, copy, staged)

    def visit(self, obj, stagedir, basedir, copy, staged=False):
        # type: (Dict[Text, Any], Text, Text, bool, bool) -> None

        source_location = obj["location"]
        target_location = convert_pathsep_to_unix(os.path.join(stagedir, obj["basename"]))

        if obj["class"] == "Directory":
            filetype = "WritableDirectory" if copy else "Directory"
            sub_resolved = obj.get("listing", [])
            sub_stagedir = target_location

            if source_location.startswith("file://"):
                resolved = uri_file_path(source_location)  # type: Text
                sub_staged = False
            else:
                resolved = source_location
                sub_staged = staged


        elif obj["class"] == "File":
            sub_resolved = obj.get("secondaryFiles", [])
            sub_stagedir = stagedir
            sub_staged = staged

            if "contents" in obj and source_location.startswith("_:"):
                filetype = "CreateWritableFile" if copy else "CreateFile"
                resolved = obj["contents"]
            else:
                filetype = "WritableFile" if copy else "File"
                resolved = abspath(source_location, basedir)

                if urllib.parse.urlsplit(resolved).scheme in ['http', 'https']:
                    with SourceLine(obj, "location",
                                    validate.ValidationException,
                                    _logger.isEnabledFor(logging.DEBUG)):
                        resolved = downloadHttpFile(source_location)
                else:
                    # Dereference symbolic links
                    st = os.lstat(resolved)
                    while stat.S_ISLNK(st.st_mode):
                        rl = os.readlink(resolved)
                        resolved = rl if os.path.isabs(rl) else os.path.join(
                            os.path.dirname(resolved), rl)
                        st = os.lstat(resolved)

        self._pathmap[source_location] = MapperEnt(resolved, target_location, filetype, staged)
        self.visitlisting(sub_resolved, sub_stagedir, basedir, copy, sub_staged)

    def _setup_pathmap(self, referenced_files, basedir, stagedir, separateDirs):
        # type: (List[Dict[Text, Any]], Text, Text, bool) -> None
        # Go through each file and set the target to its own directory along
        # with any secondary files.
        for fob in referenced_files:
            if separateDirs:
                stagedir = os.path.join(stagedir, "stg%s" % uuid.uuid4())
            self.visit(fob, stagedir, basedir, fob.get("writable", False), True)

    def mapper(self, src):  # type: (Text) -> MapperEnt
        if u"#" in src:
            i = src.index(u"#")
            p = self._pathmap[src[:i]]
            return MapperEnt(p.resolved, p.target + src[i:], p.type, p.staged)
        return self._pathmap[src]

    def files(self):  # type: () -> List[Text]
        return list(self._pathmap.keys())

    def items(self):  # type: () -> List[Tuple[Text, MapperEnt]]
        return list(self._pathmap.items())

    def reversemap(self,
                   target  # type: Text
                  ):  # type: (...) -> Optional[Tuple[Text, Text]]
        for k, v in self._pathmap.items():
            if v[1] == target:
                return (k, v[0])
        return None

    def update(self, key, resolved, target, ctype, stage):
        # type: (Text, Text, Text, Text, bool) -> None
        self._pathmap[key] = MapperEnt(resolved, target, ctype, stage)

    def __contains__(self, key):
        return key in self._pathmap
