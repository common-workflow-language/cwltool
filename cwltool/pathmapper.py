import collections
import logging
import os
import stat
import urllib
import uuid
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple, cast

from schema_salad.exceptions import ValidationException
from schema_salad.ref_resolver import uri_file_path
from schema_salad.sourceline import SourceLine

from .loghandler import _logger
from .stdfsaccess import abspath
from .utils import CWLObjectType, dedup, downloadHttpFile

MapperEnt = collections.namedtuple(
    "MapperEnt", ["resolved", "target", "type", "staged"]
)


class PathMapper:
    """
    Mapping of files from relative path provided in the file to a tuple.

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

    def __init__(
        self,
        referenced_files: List[CWLObjectType],
        basedir: str,
        stagedir: str,
        separateDirs: bool = True,
    ) -> None:
        """Initialize the PathMapper."""
        self._pathmap = {}  # type: Dict[str, MapperEnt]
        self.stagedir = stagedir
        self.separateDirs = separateDirs
        self.setup(dedup(referenced_files), basedir)

    def visitlisting(
        self,
        listing: List[CWLObjectType],
        stagedir: str,
        basedir: str,
        copy: bool = False,
        staged: bool = False,
    ) -> None:
        for ld in listing:
            self.visit(
                ld,
                stagedir,
                basedir,
                copy=cast(bool, ld.get("writable", copy)),
                staged=staged,
            )

    def visit(
        self,
        obj: CWLObjectType,
        stagedir: str,
        basedir: str,
        copy: bool = False,
        staged: bool = False,
    ) -> None:
        stagedir = cast(Optional[str], obj.get("dirname")) or stagedir
        tgt = os.path.join(
            stagedir,
            cast(str, obj["basename"]),
        )
        if obj["location"] in self._pathmap:
            return
        if obj["class"] == "Directory":
            location = cast(str, obj["location"])
            if location.startswith("file://"):
                resolved = uri_file_path(location)
            else:
                resolved = location
            self._pathmap[location] = MapperEnt(
                resolved, tgt, "WritableDirectory" if copy else "Directory", staged
            )
            if location.startswith("file://"):
                staged = False
            self.visitlisting(
                cast(List[CWLObjectType], obj.get("listing", [])),
                tgt,
                basedir,
                copy=copy,
                staged=staged,
            )
        elif obj["class"] == "File":
            path = cast(str, obj["location"])
            ab = abspath(path, basedir)
            if "contents" in obj and path.startswith("_:"):
                self._pathmap[path] = MapperEnt(
                    obj["contents"],
                    tgt,
                    "CreateWritableFile" if copy else "CreateFile",
                    staged,
                )
            else:
                with SourceLine(
                    obj,
                    "location",
                    ValidationException,
                    _logger.isEnabledFor(logging.DEBUG),
                ):
                    deref = ab
                    if urllib.parse.urlsplit(deref).scheme in ["http", "https"]:
                        deref, _last_modified = downloadHttpFile(path)
                    else:
                        # Dereference symbolic links
                        st = os.lstat(deref)
                        while stat.S_ISLNK(st.st_mode):
                            rl = os.readlink(deref)
                            deref = (
                                rl
                                if os.path.isabs(rl)
                                else os.path.join(os.path.dirname(deref), rl)
                            )
                            st = os.lstat(deref)

                    self._pathmap[path] = MapperEnt(
                        deref, tgt, "WritableFile" if copy else "File", staged
                    )
            self.visitlisting(
                cast(List[CWLObjectType], obj.get("secondaryFiles", [])),
                stagedir,
                basedir,
                copy=copy,
                staged=staged,
            )

    def setup(self, referenced_files: List[CWLObjectType], basedir: str) -> None:

        # Go through each file and set the target to its own directory along
        # with any secondary files.
        stagedir = self.stagedir
        for fob in referenced_files:
            if self.separateDirs:
                stagedir = os.path.join(self.stagedir, "stg%s" % uuid.uuid4())
            self.visit(
                fob,
                stagedir,
                basedir,
                copy=cast(bool, fob.get("writable", False)),
                staged=True,
            )

    def mapper(self, src: str) -> MapperEnt:
        if "#" in src:
            i = src.index("#")
            p = self._pathmap[src[:i]]
            return MapperEnt(p.resolved, p.target + src[i:], p.type, p.staged)
        return self._pathmap[src]

    def files(self) -> List[str]:
        return list(self._pathmap.keys())

    def items(self) -> List[Tuple[str, MapperEnt]]:
        return list(self._pathmap.items())

    def items_exclude_children(self) -> List[Tuple[str, MapperEnt]]:
        newitems = {}
        keys = [key for key, entry in self.items()]
        for key, entry in self.items():
            parents = Path(key).parents
            if any([Path(key_) in parents for key_ in keys]):
                continue
            newitems[key] = entry
        return list(newitems.items())

    def reversemap(
        self,
        target: str,
    ) -> Optional[Tuple[str, str]]:
        """Find the (source, resolved_path) for the given target, if any."""
        for k, v in self._pathmap.items():
            if v[1] == target:
                return (k, v[0])
        return None

    def update(
        self, key: str, resolved: str, target: str, ctype: str, stage: bool
    ) -> MapperEnt:
        m = MapperEnt(resolved, target, ctype, stage)
        self._pathmap[key] = m
        return m

    def __contains__(self, key: str) -> bool:
        """Test for the presence of the given relative path in this mapper."""
        return key in self._pathmap

    def __iter__(self) -> Iterator[MapperEnt]:
        """Get iterator for the maps."""
        return self._pathmap.values().__iter__()
