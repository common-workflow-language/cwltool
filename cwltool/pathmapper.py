import os
import logging
import stat
import collections
import uuid
import urllib
import urlparse
from functools import partial
from typing import Any, Callable, Set, Text, Tuple, Union
import schema_salad.validate as validate
from schema_salad.sourceline import SourceLine

_logger = logging.getLogger("cwltool")

MapperEnt = collections.namedtuple("MapperEnt", ["resolved", "target", "type"])

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

def adjustFileObjs(rec, op):  # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply an update function to each File object in the object `rec`."""

    if isinstance(rec, dict):
        if rec.get("class") == "File":
            op(rec)
        for d in rec:
            adjustFileObjs(rec[d], op)
    if isinstance(rec, list):
        for d in rec:
            adjustFileObjs(d, op)

def adjustDirObjs(rec, op):
    # type: (Any, Union[Callable[..., Any], partial[Any]]) -> None
    """Apply an update function to each Directory object in the object `rec`."""

    if isinstance(rec, dict):
        if rec.get("class") == "Directory":
            op(rec)
        for key in rec:
            adjustDirObjs(rec[key], op)
    if isinstance(rec, list):
        for d in rec:
            adjustDirObjs(d, op)

def normalizeFilesDirs(job):
    # type: (Union[List[Dict[Text, Any]], Dict[Text, Any]]) -> None
    def addLocation(d):
        if "location" not in d:
            if d["class"] == "File" and ("contents" not in d):
                raise validate.ValidationException("Anonymous file object must have 'contents' and 'basename' fields.")
            if d["class"] == "Directory" and ("listing" not in d or "basename" not in d):
                raise validate.ValidationException("Anonymous directory object must have 'listing' and 'basename' fields.")
            d["location"] = "_:" + Text(uuid.uuid4())
            if "basename" not in d:
                d["basename"] = Text(uuid.uuid4())

        if "basename" not in d:
            parse = urlparse.urlparse(d["location"])
            d["basename"] = os.path.basename(parse.path)

    adjustFileObjs(job, addLocation)
    adjustDirObjs(job, addLocation)


def abspath(src, basedir):  # type: (Text, Text) -> Text
    if src.startswith(u"file://"):
        ab = urllib.url2pathname(urlparse.urlparse(src).path)
    else:
        ab = src if os.path.isabs(src) else os.path.join(basedir, src)
    return ab

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

    def visitlisting(self, listing, stagedir, basedir):
        # type: (List[Dict[Text, Any]], Text, Text) -> None
        for ld in listing:
            tgt = os.path.join(stagedir, ld["basename"])
            if ld["class"] == "Directory":
                self.visit(ld, stagedir, basedir, copy=ld.get("writable", False))
            else:
                self.visit(ld, stagedir, basedir, copy=ld.get("writable", False))

    def visit(self, obj, stagedir, basedir, copy=False):
        # type: (Dict[Text, Any], Text, Text, bool) -> None
        tgt = os.path.join(stagedir, obj["basename"])
        if obj["class"] == "Directory":
            self._pathmap[obj["location"]] = MapperEnt(obj["location"], tgt, "Directory")
            self.visitlisting(obj.get("listing", []), tgt, basedir)
        elif obj["class"] == "File":
            path = obj["location"]
            if path in self._pathmap:
                return
            ab = abspath(path, basedir)
            if "contents" in obj and obj["location"].startswith("_:"):
                self._pathmap[obj["location"]] = MapperEnt(obj["contents"], tgt, "CreateFile")
            else:
                if copy:
                    self._pathmap[path] = MapperEnt(ab, tgt, "WritableFile")
                else:
                    with SourceLine(obj, "location", validate.ValidationException):
                        # Dereference symbolic links
                        deref = ab
                        st = os.lstat(deref)
                        while stat.S_ISLNK(st.st_mode):
                            rl = os.readlink(deref)
                            deref = rl if os.path.isabs(rl) else os.path.join(
                                os.path.dirname(deref), rl)
                            st = os.lstat(deref)

                    self._pathmap[path] = MapperEnt(deref, tgt, "File")
                self.visitlisting(obj.get("secondaryFiles", []), stagedir, basedir)

    def setup(self, referenced_files, basedir):
        # type: (List[Any], Text) -> None

        # Go through each file and set the target to its own directory along
        # with any secondary files.
        stagedir = self.stagedir
        for fob in referenced_files:
            if self.separateDirs:
                stagedir = os.path.join(self.stagedir, "stg%s" % uuid.uuid4())
            self.visit(fob, stagedir, basedir)

    def mapper(self, src):  # type: (Text) -> MapperEnt
        if u"#" in src:
            i = src.index(u"#")
            p = self._pathmap[src[:i]]
            return MapperEnt(p.resolved, p.target + src[i:], None)
        else:
            return self._pathmap[src]

    def files(self):  # type: () -> List[Text]
        return self._pathmap.keys()

    def items(self):  # type: () -> List[Tuple[Text, MapperEnt]]
        return self._pathmap.items()

    def reversemap(self, target):  # type: (Text) -> Tuple[Text, Text]
        for k, v in self._pathmap.items():
            if v[1] == target:
                return (k, v[0])
        return None
