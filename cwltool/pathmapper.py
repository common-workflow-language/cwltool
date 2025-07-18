import logging
import os
import stat
import urllib
import uuid
from collections.abc import ItemsView, Iterable, Iterator, KeysView
from typing import NamedTuple, Optional, cast

from mypy_extensions import mypyc_attr
from schema_salad.exceptions import ValidationException
from schema_salad.ref_resolver import uri_file_path
from schema_salad.sourceline import SourceLine

from .loghandler import _logger
from .stdfsaccess import abspath
from .utils import CWLObjectType, dedup, downloadHttpFile


class MapperEnt(NamedTuple):
    """Mapper entries."""

    resolved: str
    """
    The "real" path on the local file system (after resolving relative paths
    and traversing symlinks
    """
    target: str
    """The path on the target file system (under stagedir)"""
    type: Optional[str]
    """
    The object type. One of "File", "Directory", "CreateFile", "WritableFile",
    or "CreateWritableFile".
    """
    staged: Optional[bool]
    """If the File has been staged yet."""


@mypyc_attr(allow_interpreted_subclasses=True)
class PathMapper:
    """
    Mapping of files from relative path provided in the file to a tuple.

    (absolute local path, absolute container path)

    The tao of PathMapper:

    The initializer takes a list of ``class: File`` and ``class: Directory``
    objects, a base directory (for resolving relative references) and a staging
    directory (where the files are mapped to).

    The purpose of the setup method is to determine where each File or
    Directory should be placed on the target file system (relative to
    stagedir).

    If ``separatedirs=True``, unrelated files will be isolated in their own
    directories under stagedir. If ``separatedirs=False``, files and directories
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
        referenced_files: list[CWLObjectType],
        basedir: str,
        stagedir: str,
        separateDirs: bool = True,
    ) -> None:
        """Initialize the PathMapper."""
        self._pathmap: dict[str, MapperEnt] = {}
        self.stagedir = stagedir
        self.separateDirs = separateDirs
        self.setup(dedup(referenced_files), basedir)

    def visitlisting(
        self,
        listing: list[CWLObjectType],
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
        if obj["location"] in self._pathmap:
            return
        stagedir = cast(Optional[str], obj.get("dirname")) or stagedir
        tgt = os.path.join(
            stagedir,
            cast(str, obj["basename"]),
        )
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
                cast(list[CWLObjectType], obj.get("listing", [])),
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
                    cast(str, obj["contents"]),
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
                cast(list[CWLObjectType], obj.get("secondaryFiles", [])),
                stagedir,
                basedir,
                copy=copy,
                staged=staged,
            )

    def setup(self, referenced_files: list[CWLObjectType], basedir: str) -> None:
        """
        For each file, set the target to its own directory.

        Also processes secondary files into that same directory.
        """
        stagedir = self.stagedir
        for fob in referenced_files:
            if self.separateDirs:
                stagedir = os.path.join(self.stagedir, "stg%s" % uuid.uuid4())
            copy = cast(bool, fob.get("writable", False) or False)
            self.visit(
                fob,
                stagedir,
                basedir,
                copy=copy,
                staged=True,
            )

    def mapper(self, src: str) -> MapperEnt:
        if "#" in src:
            i = src.index("#")
            p = self._pathmap[src[:i]]
            return MapperEnt(p.resolved, p.target + src[i:], p.type, p.staged)
        return self._pathmap[src]

    def files(self) -> KeysView[str]:
        """Return a dictionary keys view of locations."""
        return self._pathmap.keys()

    def items(self) -> ItemsView[str, MapperEnt]:
        """Return a dictionary items view."""
        return self._pathmap.items()

    def items_exclude_children(self) -> ItemsView[str, MapperEnt]:
        """Return a dictionary items view minus any entries which are children of other entries."""
        newitems = {}

        def parents(path: str) -> Iterable[str]:
            result = path
            while len(result) > 1:
                result = os.path.dirname(result)
                yield result

        for key, entry in self.items():
            if not self.files().isdisjoint(parents(key)):
                continue
            newitems[key] = entry
        return newitems.items()

    def reversemap(
        self,
        target: str,
    ) -> Optional[tuple[str, str]]:
        """Find the (source, resolved_path) for the given target, if any."""
        for k, v in self._pathmap.items():
            if v[1] == target:
                return (k, v[0])
        return None

    def update(
        self, key: str, resolved: str, target: str, ctype: Optional[str], stage: Optional[bool]
    ) -> MapperEnt:
        """Update an existing entry."""
        m = MapperEnt(resolved, target, ctype, stage)
        self._pathmap[key] = m
        return m

    def __contains__(self, key: str) -> bool:
        """Test for the presence of the given relative path in this mapper."""
        return key in self._pathmap

    def __iter__(self) -> Iterator[MapperEnt]:
        """Get iterator for the maps."""
        return self._pathmap.values().__iter__()
