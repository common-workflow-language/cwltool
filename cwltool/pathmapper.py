import os
import logging
import stat
import collections
import uuid
from typing import Tuple, Set, Union, Any

_logger = logging.getLogger("cwltool")

MapperEnt = collections.namedtuple("MapperEnt", ("resolved", "target", "type"))

def adjustFiles(rec, op):  # type: (Any, Callable[..., Any]) -> None
    """Apply a mapping function to each File path in the object `rec`."""

    if isinstance(rec, dict):
        if rec.get("class") == "File":
            rec["path"] = op(rec["path"])
        for d in rec:
            adjustFiles(rec[d], op)
    if isinstance(rec, list):
        for d in rec:
            adjustFiles(d, op)

def adjustFileObjs(rec, op):  # type: (Any, Callable[[Any], Any]) -> None
    """Apply an update function to each File object in the object `rec`."""

    if isinstance(rec, dict):
        if rec.get("class") == "File":
            op(rec)
        for d in rec:
            adjustFileObjs(rec[d], op)
    if isinstance(rec, list):
        for d in rec:
            adjustFileObjs(d, op)

def adjustDirObjs(rec, op):  # type: (Any, Callable[[Any], Any]) -> None
    """Apply an update function to each Directory object in the object `rec`."""

    if isinstance(rec, dict):
        if rec.get("class") == "Directory":
            op(rec)
        for d in rec:
            adjustDirObjs(rec[d], op)
    if isinstance(rec, list):
        for d in rec:
            adjustDirObjs(d, op)


def abspath(src, basedir):  # type: (unicode, unicode) -> unicode
    if src.startswith(u"file://"):
        ab = src[7:]
    else:
        ab = src if os.path.isabs(src) else os.path.join(basedir, src)
    return ab


class PathMapper(object):

    """Mapping of files from relative path provided in the file to a tuple of
    (absolute local path, absolute container path)"""

    def __init__(self, referenced_files, basedir, stagedir, separateDirs=True):
        # type: (Set[Any], unicode, unicode) -> None
        self._pathmap = {}  # type: Dict[unicode, Tuple[unicode, unicode]]
        self.stagedir = stagedir
        self.separateDirs = separateDirs
        self.setup(referenced_files, basedir)

    def visitlisting(self, listing, stagedir, basedir):
        for ld in listing:
            tgt = os.path.join(stagedir, ld["basename"])
            if "contents" in ld and ld["location"].startswith("_:"):
                self._pathmap[ld["location"]] = MapperEnt(ld["contents"], tgt, "CreateFile")
            else:
                if ld["class"] == "Directory":
                    self.visit(ld, tgt, basedir, copy=ld.get("writable", False))
                else:
                    self.visit(ld, stagedir, basedir, copy=ld.get("writable", False))

    def visit(self, obj, stagedir, basedir, copy=False):
        if obj["class"] == "Directory":
            self._pathmap[obj["location"]] = MapperEnt(obj["location"], stagedir, "Directory")
            self.visitlisting(obj.get("listing", []), stagedir, basedir)
        elif obj["class"] == "File":
            path = obj["location"]
            if path in self._pathmap:
                return
            ab = abspath(path, basedir)
            tgt = os.path.join(stagedir, obj["basename"])
            if copy:
                self._pathmap[path] = MapperEnt(ab, tgt, "WritableFile")
            else:
                self._pathmap[path] = MapperEnt(ab, tgt, "File")
            self.visitlisting(obj.get("secondaryFiles", []), stagedir, basedir)

    def setup(self, referenced_files, basedir):
        # type: (Set[Any], unicode) -> None

        # Go through each file and set the target to its own directory along
        # with any secondary files.
        stagedir = self.stagedir
        for fob in referenced_files:
            if self.separateDirs:
                stagedir = os.path.join(self.stagedir, "stg%s" % uuid.uuid4())
            self.visit(fob, stagedir, basedir)

        # Dereference symbolic links
        for path, (ab, tgt, type) in self._pathmap.items():
            if type != "File": # or not os.path.exists(ab):
                continue
            deref = ab
            st = os.lstat(deref)
            while stat.S_ISLNK(st.st_mode):
                rl = os.readlink(deref)
                deref = rl if os.path.isabs(rl) else os.path.join(
                        os.path.dirname(deref), rl)
                st = os.lstat(deref)

            self._pathmap[path] = MapperEnt(deref, tgt, "File")

    def mapper(self, src):  # type: (unicode) -> Tuple[unicode, unicode]
        if u"#" in src:
            i = src.index(u"#")
            p = self._pathmap[src[:i]]
            return (p.resolved, p.target + src[i:])
        else:
            return self._pathmap[src]

    def files(self):  # type: () -> List[unicode]
        return self._pathmap.keys()

    def items(self):  # type: () -> List[Tuple[unicode, Tuple[unicode, unicode]]]
        return self._pathmap.items()

    def reversemap(self, target):  # type: (unicode) -> Tuple[unicode, unicode]
        for k, v in self._pathmap.items():
            if v[1] == target:
                return (k, v[0])
        return None
