import os
import random
import logging
import stat
from typing import Tuple, Set, Union, Any

_logger = logging.getLogger("cwltool")

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


def abspath(src, basedir):  # type: (unicode, unicode) -> unicode
    if src.startswith(u"file://"):
        ab = src[7:]
    else:
        ab = src if os.path.isabs(src) else os.path.join(basedir, src)
    return ab


class PathMapper(object):

    """Mapping of files from relative path provided in the file to a tuple of
    (absolute local path, absolute container path)"""

    def __init__(self, referenced_files, basedir, stagedir, scramble=False):
        # type: (Set[Any], unicode, unicode) -> None
        self._pathmap = {}  # type: Dict[unicode, Tuple[unicode, unicode]]
        self.stagedir = stagedir
        self.scramble = scramble
        self.setup(referenced_files, basedir)

    def setup(self, referenced_files, basedir):
        # type: (Set[Any], unicode) -> None

        # Go through each file and set the target to its own directory along
        # with any secondary files.
        for fob in referenced_files:
            stagedir = os.path.join(self.stagedir, "stg%x" % random.randint(1, 1000000000))

            if fob["class"] == "Directory":
                def visit(obj, base):
                    self._pathmap[obj["id"]] = (obj["id"], base)
                    for ld in obj["listing"]:
                        tgt = os.path.join(base, ld["basename"])
                        if ld["entry"]["class"] == "Directory":
                            visit(ld["entry"], tgt)
                            ab = ld["entry"]["id"]
                            self._pathmap[ab] = (ab, tgt)
                        else:
                            ab = ld["entry"]["path"]
                            self._pathmap[ab] = (ab, tgt)

                visit(fob, stagedir)
            else:
                def visit(path):
                    if path in self._pathmap:
                        return path
                    ab = abspath(path, basedir)
                    if self.scramble:
                        tgt = os.path.join(stagedir, "inp%x.dat" % random.randint(1, 1000000000))
                    else:
                        tgt = os.path.join(stagedir, os.path.basename(path))
                    self._pathmap[path] = (ab, tgt)
                    return path

                adjustFiles(fob, visit)

        # Dereference symbolic links
        for path, (ab, tgt) in self._pathmap.items():
            if ab.startswith("_dir:"):
                continue
            deref = ab
            st = os.lstat(deref)
            while stat.S_ISLNK(st.st_mode):
                rl = os.readlink(deref)
                deref = rl if os.path.isabs(rl) else os.path.join(
                        os.path.dirname(deref), rl)
                st = os.lstat(deref)

            self._pathmap[path] = (deref, tgt)

    def mapper(self, src):  # type: (unicode) -> Tuple[unicode, unicode]
        if u"#" in src:
            i = src.index(u"#")
            p = self._pathmap[src[:i]]
            return (p[0], p[1] + src[i:])
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
