import os
import random
import logging
import stat
from typing import Tuple, Set, Union, Any

_logger = logging.getLogger("cwltool")


def abspath(src, basedir):  # type: (str,str) -> str
    if src.startswith("file://"):
        ab = src[7:]
    else:
        ab = src if os.path.isabs(src) else os.path.join(basedir, src)
    return ab


class PathMapper(object):

    """Mapping of files from relative path provided in the file to a tuple of
    (absolute local path, absolute container path)"""

    def __init__(self, referenced_files, basedir):
        # type: (Set[str], str) -> None
        self._pathmap = {}  # type: Dict[str, Tuple[str, str]]
        self.setup(referenced_files, basedir)

    def setup(self, referenced_files, basedir):
        # type: (Set[str], str) -> None
        for src in referenced_files:
            ab = abspath(src, basedir)
            self._pathmap[src] = (ab, ab)

    def mapper(self, src):  # type: (str) -> Tuple[str,str]
        if "#" in src:
            i = src.index("#")
            p = self._pathmap[src[:i]]
            return (p[0], p[1] + src[i:])
        else:
            return self._pathmap[src]

    def files(self):  # type: () -> List[str]
        return self._pathmap.keys()

    def items(self):  # type: () -> List[Tuple[str,Tuple[str,str]]]
        return self._pathmap.items()

    def reversemap(self, target):  # type: (str) -> Tuple[str, str]
        for k, v in self._pathmap.items():
            if v[1] == target:
                return (k, v[0])
        return None


class DockerPathMapper(PathMapper):

    def __init__(self, referenced_files, basedir):
        # type: (Set[str], str) -> None
        self.dirs = {}  # type: Dict[str, Union[bool, str]]
        super(DockerPathMapper, self).__init__(referenced_files, basedir)

    def setup(self, referenced_files, basedir):
        for src in referenced_files:
            ab = abspath(src, basedir)
            dirn, fn = os.path.split(ab)

            subdir = False
            for d in self.dirs:
                if dirn.startswith(d):
                  subdir = True
                  break

            if not subdir:
                for d in list(self.dirs):
                    if d.startswith(dirn):
                        # 'dirn' is a parent of 'd'
                        del self.dirs[d]
                self.dirs[dirn] = True

        prefix = "job" + str(random.randint(1, 1000000000)) + "_"

        names = set()  # type: Set[str]
        for d in self.dirs:
            name = os.path.join("/var/lib/cwl", prefix + os.path.basename(d))
            i = 1
            while name in names:
                i += 1
                name = os.path.join("/var/lib/cwl",
                        prefix + os.path.basename(d) + str(i))
            names.add(name)
            self.dirs[d] = name

        for src in referenced_files:
            ab = abspath(src, basedir)

            deref = ab
            st = os.lstat(deref)
            while stat.S_ISLNK(st.st_mode):
                rl = os.readlink(deref)
                deref = rl if os.path.isabs(rl) else os.path.join(
                        os.path.dirname(deref), rl)
                st = os.lstat(deref)

            for d in self.dirs:
                if ab.startswith(d):
                    self._pathmap[src] = (deref, os.path.join(
                        self.dirs[d], ab[len(d)+1:]))
