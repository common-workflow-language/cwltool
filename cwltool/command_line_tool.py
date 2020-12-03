"""Implementation of CommandLineTool."""

import copy
import hashlib
import json
import locale
import logging
import os
import re
import shutil
import threading
import urllib
from functools import cmp_to_key, partial
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Set,
    TextIO,
    Union,
    cast,
)

import shellescape
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.avro.schema import Schema
from schema_salad.exceptions import ValidationException
from schema_salad.ref_resolver import file_uri, uri_file_path
from schema_salad.sourceline import SourceLine
from schema_salad.utils import json_dumps
from schema_salad.validate import validate_ex
from typing_extensions import TYPE_CHECKING, Type

from .builder import Builder, content_limit_respected_read_bytes, substitute
from .context import LoadingContext, RuntimeContext, getdefault
from .docker import DockerCommandLineJob
from .errors import UnsupportedRequirement, WorkflowException
from .flatten import flatten
from .job import CommandLineJob, JobBase
from .loghandler import _logger
from .mpi import MPIRequirementName
from .mutation import MutationManager
from .pathmapper import PathMapper
from .process import (
    Process,
    _logger_validation_warnings,
    compute_checksums,
    shortname,
    uniquename,
)
from .singularity import SingularityCommandLineJob
from .stdfsaccess import StdFsAccess
from .udocker import UDockerCommandLineJob
from .update import ORDERED_VERSIONS
from .utils import (
    CWLObjectType,
    CWLOutputType,
    DirectoryType,
    JobsGeneratorType,
    OutputCallbackType,
    adjustDirObjs,
    adjustFileObjs,
    aslist,
    convert_pathsep_to_unix,
    docker_windows_path_adjust,
    get_listing,
    normalizeFilesDirs,
    onWindows,
    random_outdir,
    shared_file_lock,
    trim_listing,
    upgrade_lock,
    visit_class,
    windows_default_container_id,
)

if TYPE_CHECKING:
    from .provenance_profile import ProvenanceProfile  # pylint: disable=unused-import

ACCEPTLIST_EN_STRICT_RE = re.compile(r"^[a-zA-Z0-9._+-]+$")
ACCEPTLIST_EN_RELAXED_RE = re.compile(r".*")  # Accept anything
ACCEPTLIST_RE = ACCEPTLIST_EN_STRICT_RE
DEFAULT_CONTAINER_MSG = """
We are on Microsoft Windows and not all components of this CWL description have a
container specified. This means that these steps will be executed in the default container,
which is %s.

Note, this could affect portability if this CWL description relies on non-POSIX features
or commands in this container. For best results add the following to your CWL
description's hints section:

hints:
  DockerRequirement:
    dockerPull: %s
"""


class ExpressionJob(object):
    """Job for ExpressionTools."""

    def __init__(
        self,
        builder: Builder,
        script: str,
        output_callback: Optional[OutputCallbackType],
        requirements: List[CWLObjectType],
        hints: List[CWLObjectType],
        outdir: Optional[str] = None,
        tmpdir: Optional[str] = None,
    ) -> None:
        """Initializet this ExpressionJob."""
        self.builder = builder
        self.requirements = requirements
        self.hints = hints
        self.output_callback = output_callback
        self.outdir = outdir
        self.tmpdir = tmpdir
        self.script = script
        self.prov_obj = None  # type: Optional[ProvenanceProfile]

    def run(
        self,
        runtimeContext: RuntimeContext,
        tmpdir_lock: Optional[threading.Lock] = None,
    ) -> None:
        try:
            normalizeFilesDirs(self.builder.job)
            ev = self.builder.do_eval(self.script)
            normalizeFilesDirs(
                cast(
                    Optional[
                        Union[
                            MutableSequence[MutableMapping[str, Any]],
                            MutableMapping[str, Any],
                            DirectoryType,
                        ]
                    ],
                    ev,
                )
            )
            if self.output_callback:
                self.output_callback(cast(Optional[CWLObjectType], ev), "success")
        except WorkflowException as err:
            _logger.warning(
                "Failed to evaluate expression:\n%s",
                str(err),
                exc_info=runtimeContext.debug,
            )
            if self.output_callback:
                self.output_callback({}, "permanentFail")


class ExpressionTool(Process):
    def job(
        self,
        job_order: CWLObjectType,
        output_callbacks: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> Generator[ExpressionJob, None, None]:
        builder = self._init_job(job_order, runtimeContext)

        job = ExpressionJob(
            builder,
            self.tool["expression"],
            output_callbacks,
            self.requirements,
            self.hints,
        )
        job.prov_obj = runtimeContext.prov_obj
        yield job


class AbstractOperation(Process):
    def job(
        self,
        job_order: CWLObjectType,
        output_callbacks: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> JobsGeneratorType:
        raise WorkflowException("Abstract operation cannot be executed.")


def remove_path(f):  # type: (CWLObjectType) -> None
    if "path" in f:
        del f["path"]


def revmap_file(
    builder: Builder, outdir: str, f: CWLObjectType
) -> Optional[CWLObjectType]:
    """
    Remap a file from internal path to external path.

    For Docker, this maps from the path inside tho container to the path
    outside the container. Recognizes files in the pathmapper or remaps
    internal output directories to the external directory.
    """
    split = urllib.parse.urlsplit(outdir)
    if not split.scheme:
        outdir = file_uri(str(outdir))

    # builder.outdir is the inner (container/compute node) output directory
    # outdir is the outer (host/storage system) output directory

    if "location" in f and "path" not in f:
        location = cast(str, f["location"])
        if location.startswith("file://"):
            f["path"] = convert_pathsep_to_unix(uri_file_path(location))
        else:
            return f

    if "dirname" in f:
        del f["dirname"]

    if "path" in f:
        path = cast(str, f["path"])
        uripath = file_uri(path)
        del f["path"]

        if "basename" not in f:
            f["basename"] = os.path.basename(path)

        if not builder.pathmapper:
            raise ValueError(
                "Do not call revmap_file using a builder that doesn't have a pathmapper."
            )
        revmap_f = builder.pathmapper.reversemap(path)

        if revmap_f and not builder.pathmapper.mapper(revmap_f[0]).type.startswith(
            "Writable"
        ):
            f["location"] = revmap_f[1]
        elif (
            uripath == outdir
            or uripath.startswith(outdir + os.sep)
            or uripath.startswith(outdir + "/")
        ):
            f["location"] = file_uri(path)
        elif (
            path == builder.outdir
            or path.startswith(builder.outdir + os.sep)
            or path.startswith(builder.outdir + "/")
        ):
            f["location"] = builder.fs_access.join(
                outdir, path[len(builder.outdir) + 1 :]
            )
        elif not os.path.isabs(path):
            f["location"] = builder.fs_access.join(outdir, path)
        else:
            raise WorkflowException(
                "Output file path %s must be within designated output directory (%s) or an input "
                "file pass through." % (path, builder.outdir)
            )
        return f

    raise WorkflowException(
        "Output File object is missing both 'location' and 'path' fields: %s" % f
    )


class CallbackJob(object):
    def __init__(
        self,
        job: "CommandLineTool",
        output_callback: Optional[OutputCallbackType],
        cachebuilder: Builder,
        jobcache: str,
    ) -> None:
        """Initialize this CallbackJob."""
        self.job = job
        self.output_callback = output_callback
        self.cachebuilder = cachebuilder
        self.outdir = jobcache
        self.prov_obj = None  # type: Optional[ProvenanceProfile]

    def run(
        self,
        runtimeContext: RuntimeContext,
        tmpdir_lock: Optional[threading.Lock] = None,
    ) -> None:
        if self.output_callback:
            self.output_callback(
                self.job.collect_output_ports(
                    self.job.tool["outputs"],
                    self.cachebuilder,
                    self.outdir,
                    getdefault(runtimeContext.compute_checksum, True),
                ),
                "success",
            )


def check_adjust(builder: Builder, file_o: CWLObjectType) -> CWLObjectType:
    """
    Map files to assigned path inside a container.

    We need to also explicitly walk over input, as implicit reassignment
    doesn't reach everything in builder.bindings
    """
    if not builder.pathmapper:
        raise ValueError(
            "Do not call check_adjust using a builder that doesn't have a pathmapper."
        )
    file_o["path"] = path = docker_windows_path_adjust(
        builder.pathmapper.mapper(cast(str, file_o["location"]))[1]
    )
    basename = cast(str, file_o.get("basename"))
    dn, bn = os.path.split(path)
    if file_o.get("dirname") != dn:
        file_o["dirname"] = str(dn)
    if basename != bn:
        file_o["basename"] = basename = str(bn)
    if file_o["class"] == "File":
        nr, ne = os.path.splitext(basename)
        if file_o.get("nameroot") != nr:
            file_o["nameroot"] = str(nr)
        if file_o.get("nameext") != ne:
            file_o["nameext"] = str(ne)
    if not ACCEPTLIST_RE.match(basename):
        raise WorkflowException(
            "Invalid filename: '{}' contains illegal characters".format(
                file_o["basename"]
            )
        )
    return file_o


def check_valid_locations(fs_access: StdFsAccess, ob: CWLObjectType) -> None:
    location = cast(str, ob["location"])
    if location.startswith("_:"):
        pass
    if ob["class"] == "File" and not fs_access.isfile(location):
        raise ValidationException("Does not exist or is not a File: '%s'" % location)
    if ob["class"] == "Directory" and not fs_access.isdir(location):
        raise ValidationException(
            "Does not exist or is not a Directory: '%s'" % location
        )


OutputPortsType = Dict[str, Optional[CWLOutputType]]


class ParameterOutputWorkflowException(WorkflowException):
    def __init__(self, msg: str, port: CWLObjectType, **kwargs: Any) -> None:
        """Exception for when there was an error collecting output for a parameter."""
        super(ParameterOutputWorkflowException, self).__init__(
            "Error collecting output for parameter '%s':\n%s"
            % (shortname(cast(str, port["id"])), msg),
            kwargs,
        )


class CommandLineTool(Process):
    def __init__(
        self, toolpath_object: CommentedMap, loadingContext: LoadingContext
    ) -> None:
        """Initialize this CommandLineTool."""
        super(CommandLineTool, self).__init__(toolpath_object, loadingContext)
        self.prov_obj = loadingContext.prov_obj

    def make_job_runner(self, runtimeContext: RuntimeContext) -> Type[JobBase]:
        dockerReq, dockerRequired = self.get_requirement("DockerRequirement")
        mpiReq, mpiRequired = self.get_requirement(MPIRequirementName)

        if not dockerReq and runtimeContext.use_container:
            if runtimeContext.find_default_container is not None:
                default_container = runtimeContext.find_default_container(self)
                if default_container is not None:
                    dockerReq = {
                        "class": "DockerRequirement",
                        "dockerPull": default_container,
                    }
                    if mpiRequired:
                        self.hints.insert(0, dockerReq)
                        dockerRequired = False
                    else:
                        self.requirements.insert(0, dockerReq)
                        dockerRequired = True

                    if (
                        default_container == windows_default_container_id
                        and runtimeContext.use_container
                        and onWindows()
                    ):
                        _logger.warning(
                            DEFAULT_CONTAINER_MSG,
                            windows_default_container_id,
                            windows_default_container_id,
                        )

        if dockerReq is not None and runtimeContext.use_container:
            if mpiReq is not None:
                _logger.warning("MPIRequirement with containers is a beta feature")
            if runtimeContext.singularity:
                return SingularityCommandLineJob
            elif runtimeContext.user_space_docker_cmd:
                return UDockerCommandLineJob
            if mpiReq is not None:
                if mpiRequired:
                    if dockerRequired:
                        raise UnsupportedRequirement(
                            "No support for Docker and MPIRequirement both being required"
                        )
                    else:
                        _logger.warning(
                            "MPI has been required while Docker is hinted, discarding Docker hint(s)"
                        )
                        self.hints = [
                            h for h in self.hints if h["class"] != "DockerRequirement"
                        ]
                        return CommandLineJob
                else:
                    if dockerRequired:
                        _logger.warning(
                            "Docker has been required while MPI is hinted, discarding MPI hint(s)"
                        )
                        self.hints = [
                            h for h in self.hints if h["class"] != MPIRequirementName
                        ]
                    else:
                        raise UnsupportedRequirement(
                            "Both Docker and MPI have been hinted - don't know what to do"
                        )
            return DockerCommandLineJob
        if dockerRequired:
            raise UnsupportedRequirement(
                "--no-container, but this CommandLineTool has "
                "DockerRequirement under 'requirements'."
            )
        return CommandLineJob

    def make_path_mapper(
        self,
        reffiles: List[CWLObjectType],
        stagedir: str,
        runtimeContext: RuntimeContext,
        separateDirs: bool,
    ) -> PathMapper:
        return PathMapper(reffiles, runtimeContext.basedir, stagedir, separateDirs)

    def updatePathmap(
        self, outdir: str, pathmap: PathMapper, fn: CWLObjectType
    ) -> None:
        if not isinstance(fn, MutableMapping):
            raise WorkflowException(
                "Expected File or Directory object, was %s" % type(fn)
            )
        basename = cast(str, fn["basename"])
        if "location" in fn:
            location = cast(str, fn["location"])
            if location in pathmap:
                pathmap.update(
                    location,
                    pathmap.mapper(location).resolved,
                    os.path.join(outdir, basename),
                    ("Writable" if fn.get("writable") else "") + cast(str, fn["class"]),
                    False,
                )
        for sf in cast(List[CWLObjectType], fn.get("secondaryFiles", [])):
            self.updatePathmap(outdir, pathmap, sf)
        for ls in cast(List[CWLObjectType], fn.get("listing", [])):
            self.updatePathmap(
                os.path.join(outdir, cast(str, fn["basename"])), pathmap, ls
            )

    def _initialworkdir(self, j: JobBase, builder: Builder) -> None:
        initialWorkdir, _ = self.get_requirement("InitialWorkDirRequirement")
        if initialWorkdir is None:
            return

        ls = []  # type: List[CWLObjectType]
        if isinstance(initialWorkdir["listing"], str):
            # "listing" is just a string (must be an expression) so
            # just evaluate it and use the result as if it was in
            # listing
            ls = cast(List[CWLObjectType], builder.do_eval(initialWorkdir["listing"]))
        else:
            # "listing" is an array of either expressions or Dirent so
            # evaluate each item
            for t in cast(
                MutableSequence[Union[str, CWLObjectType]],
                initialWorkdir["listing"],
            ):
                if isinstance(t, Mapping) and "entry" in t:
                    # Dirent
                    entry = builder.do_eval(
                        cast(str, t["entry"]), strip_whitespace=False
                    )
                    if entry is None:
                        continue

                    if isinstance(entry, MutableSequence):
                        # Nested list.  If it is a list of File or
                        # Directory objects, add it to the
                        # file list, otherwise JSON serialize it.
                        filelist = True
                        for e in entry:
                            if not isinstance(e, MutableMapping) or e.get(
                                "class"
                            ) not in ("File", "Directory"):
                                filelist = False
                                break

                        if filelist:
                            if "entryname" in t:
                                raise SourceLine(
                                    t, "entryname", WorkflowException
                                ).makeError(
                                    "'entryname' is invalid when 'entry' returns list of File or Directory"
                                )
                            for e in entry:
                                ec = cast(CWLObjectType, e)
                                ec["writeable"] = t.get("writable", False)
                            ls.extend(cast(List[CWLObjectType], entry))
                            continue

                    et = {}  # type: CWLObjectType
                    if isinstance(entry, Mapping) and entry.get("class") in (
                        "File",
                        "Directory",
                    ):
                        et["entry"] = entry
                    else:
                        et["entry"] = (
                            entry
                            if isinstance(entry, str)
                            else json_dumps(entry, sort_keys=True)
                        )

                    if "entryname" in t:
                        en = builder.do_eval(cast(str, t["entryname"]))
                        if not isinstance(en, str):
                            raise SourceLine(
                                t, "entryname", WorkflowException
                            ).makeError("'entryname' must be a string")
                        et["entryname"] = en
                    else:
                        et["entryname"] = None
                    et["writable"] = t.get("writable", False)
                    ls.append(et)
                else:
                    # Expression, must return a Dirent, File, Directory
                    # or array of such.
                    initwd_item = builder.do_eval(t)
                    if not initwd_item:
                        continue
                    if isinstance(initwd_item, MutableSequence):
                        ls.extend(cast(List[CWLObjectType], initwd_item))
                    else:
                        ls.append(cast(CWLObjectType, initwd_item))

        for i, t2 in enumerate(ls):
            if not isinstance(t2, Mapping):
                raise SourceLine(
                    initialWorkdir, "listing", WorkflowException
                ).makeError(
                    "Entry at index %s of listing is not a record, was %s"
                    % (i, type(t2))
                )

            if "entry" not in t2:
                continue

            # Dirent
            if isinstance(t2["entry"], str):
                if not t2["entryname"]:
                    raise SourceLine(
                        initialWorkdir, "listing", WorkflowException
                    ).makeError("Entry at index %s of listing missing entryname" % (i))
                ls[i] = {
                    "class": "File",
                    "basename": t2["entryname"],
                    "contents": t2["entry"],
                    "writable": t2.get("writable"),
                }
                continue

            if not isinstance(t2["entry"], Mapping):
                raise SourceLine(
                    initialWorkdir, "listing", WorkflowException
                ).makeError(
                    "Entry at index %s of listing is not a record, was %s"
                    % (i, type(t2["entry"]))
                )

            if t2["entry"].get("class") not in ("File", "Directory"):
                raise SourceLine(
                    initialWorkdir, "listing", WorkflowException
                ).makeError(
                    "Entry at index %s of listing is not a File or Directory object, was %s"
                    % (i, t2)
                )

            if t2.get("entryname") or t2.get("writable"):
                t2 = copy.deepcopy(t2)
                t2entry = cast(CWLObjectType, t2["entry"])
                if t2.get("entryname"):
                    t2entry["basename"] = t2["entryname"]
                t2entry["writable"] = t2.get("writable")

            ls[i] = cast(CWLObjectType, t2["entry"])

        for i, t3 in enumerate(ls):
            if t3.get("class") not in ("File", "Directory"):
                # Check that every item is a File or Directory object now
                raise SourceLine(
                    initialWorkdir, "listing", WorkflowException
                ).makeError(
                    "Entry at index %s of listing is not a Dirent, File or Directory object, was %s"
                    % (i, t2)
                )
            if "basename" not in t3:
                continue
            basename = os.path.normpath(cast(str, t3["basename"]))
            t3["basename"] = basename
            if basename.startswith("../"):
                raise SourceLine(
                    initialWorkdir, "listing", WorkflowException
                ).makeError(
                    "Name '%s' at index %s of listing is invalid, cannot start with '../'"
                    % (basename, i)
                )
            if basename.startswith("/"):
                # only if DockerRequirement in requirements
                cwl_version = self.metadata.get(
                    "http://commonwl.org/cwltool#original_cwlVersion", None
                )
                if isinstance(cwl_version, str) and ORDERED_VERSIONS.index(
                    cwl_version
                ) < ORDERED_VERSIONS.index("v1.2.0-dev4"):
                    raise SourceLine(
                        initialWorkdir, "listing", WorkflowException
                    ).makeError(
                        "Name '%s' at index %s of listing is invalid, paths starting with '/' only permitted in CWL 1.2 and later"
                        % (basename, i)
                    )

                req, is_req = self.get_requirement("DockerRequirement")
                if is_req is not True:
                    raise SourceLine(
                        initialWorkdir, "listing", WorkflowException
                    ).makeError(
                        "Name '%s' at index %s of listing is invalid, name can only start with '/' when DockerRequirement is in 'requirements'"
                        % (basename, i)
                    )

        with SourceLine(initialWorkdir, "listing", WorkflowException):
            j.generatefiles["listing"] = ls
            for entry in ls:
                if "basename" in entry:
                    basename = cast(str, entry["basename"])
                    entry["dirname"] = os.path.join(
                        builder.outdir, os.path.dirname(basename)
                    )
                    entry["basename"] = os.path.basename(basename)
                normalizeFilesDirs(entry)
                self.updatePathmap(
                    cast(Optional[str], entry.get("dirname")) or builder.outdir,
                    cast(PathMapper, builder.pathmapper),
                    entry,
                )
                if "listing" in entry:

                    def remove_dirname(d: CWLObjectType) -> None:
                        if "dirname" in d:
                            del d["dirname"]

                    visit_class(
                        entry["listing"],
                        ("File", "Directory"),
                        remove_dirname,
                    )

            visit_class(
                [builder.files, builder.bindings],
                ("File", "Directory"),
                partial(check_adjust, builder),
            )

    def job(
        self,
        job_order: CWLObjectType,
        output_callbacks: Optional[OutputCallbackType],
        runtimeContext: RuntimeContext,
    ) -> Generator[Union[JobBase, CallbackJob], None, None]:

        workReuse, _ = self.get_requirement("WorkReuse")
        enableReuse = workReuse.get("enableReuse", True) if workReuse else True

        jobname = uniquename(
            runtimeContext.name or shortname(self.tool.get("id", "job"))
        )
        if runtimeContext.cachedir and enableReuse:
            cachecontext = runtimeContext.copy()
            cachecontext.outdir = "/out"
            cachecontext.tmpdir = "/tmp"  # nosec
            cachecontext.stagedir = "/stage"
            cachebuilder = self._init_job(job_order, cachecontext)
            cachebuilder.pathmapper = PathMapper(
                cachebuilder.files,
                runtimeContext.basedir,
                cachebuilder.stagedir,
                separateDirs=False,
            )
            _check_adjust = partial(check_adjust, cachebuilder)
            visit_class(
                [cachebuilder.files, cachebuilder.bindings],
                ("File", "Directory"),
                _check_adjust,
            )

            cmdline = flatten(
                list(map(cachebuilder.generate_arg, cachebuilder.bindings))
            )
            docker_req, _ = self.get_requirement("DockerRequirement")
            if docker_req is not None and runtimeContext.use_container:
                dockerimg = docker_req.get("dockerImageId") or docker_req.get(
                    "dockerPull"
                )
            elif (
                runtimeContext.default_container is not None
                and runtimeContext.use_container
            ):
                dockerimg = runtimeContext.default_container
            else:
                dockerimg = None

            if dockerimg is not None:
                cmdline = ["docker", "run", dockerimg] + cmdline
                # not really run using docker, just for hashing purposes

            keydict = {
                "cmdline": cmdline
            }  # type: Dict[str, Union[MutableSequence[Union[str, int]], CWLObjectType]]

            for shortcut in ["stdin", "stdout", "stderr"]:
                if shortcut in self.tool:
                    keydict[shortcut] = self.tool[shortcut]

            def calc_checksum(location: str) -> Optional[str]:
                for e in cachebuilder.files:
                    if (
                        "location" in e
                        and e["location"] == location
                        and "checksum" in e
                        and e["checksum"] != "sha1$hash"
                    ):
                        return cast(Optional[str], e["checksum"])
                return None

            for location, fobj in cachebuilder.pathmapper.items():
                if fobj.type == "File":
                    checksum = calc_checksum(location)
                    fobj_stat = os.stat(fobj.resolved)
                    if checksum is not None:
                        keydict[fobj.resolved] = [fobj_stat.st_size, checksum]
                    else:
                        keydict[fobj.resolved] = [
                            fobj_stat.st_size,
                            int(fobj_stat.st_mtime * 1000),
                        ]

            interesting = {
                "DockerRequirement",
                "EnvVarRequirement",
                "InitialWorkDirRequirement",
                "ShellCommandRequirement",
                "NetworkAccess",
            }
            for rh in (self.original_requirements, self.original_hints):
                for r in reversed(rh):
                    cls = cast(str, r["class"])
                    if cls in interesting and cls not in keydict:
                        keydict[cls] = r

            keydictstr = json_dumps(keydict, separators=(",", ":"), sort_keys=True)
            cachekey = hashlib.md5(keydictstr.encode("utf-8")).hexdigest()  # nosec

            _logger.debug(
                "[job %s] keydictstr is %s -> %s", jobname, keydictstr, cachekey
            )

            jobcache = os.path.join(runtimeContext.cachedir, cachekey)

            # Create a lockfile to manage cache status.
            jobcachepending = "{}.status".format(jobcache)
            jobcachelock = None
            jobstatus = None

            # Opens the file for read/write, or creates an empty file.
            jobcachelock = open(jobcachepending, "a+")

            # get the shared lock to ensure no other process is trying
            # to write to this cache
            shared_file_lock(jobcachelock)
            jobcachelock.seek(0)
            jobstatus = jobcachelock.read()

            if os.path.isdir(jobcache) and jobstatus == "success":
                if docker_req and runtimeContext.use_container:
                    cachebuilder.outdir = (
                        runtimeContext.docker_outdir or random_outdir()
                    )
                else:
                    cachebuilder.outdir = jobcache

                _logger.info("[job %s] Using cached output in %s", jobname, jobcache)
                yield CallbackJob(self, output_callbacks, cachebuilder, jobcache)
                # we're done with the cache so release lock
                jobcachelock.close()
                return
            else:
                _logger.info(
                    "[job %s] Output of job will be cached in %s", jobname, jobcache
                )

                # turn shared lock into an exclusive lock since we'll
                # be writing the cache directory
                upgrade_lock(jobcachelock)

                shutil.rmtree(jobcache, True)
                os.makedirs(jobcache)
                runtimeContext = runtimeContext.copy()
                runtimeContext.outdir = jobcache

                def update_status_output_callback(
                    output_callbacks: OutputCallbackType,
                    jobcachelock: TextIO,
                    outputs: Optional[CWLObjectType],
                    processStatus: str,
                ) -> None:
                    # save status to the lockfile then release the lock
                    jobcachelock.seek(0)
                    jobcachelock.truncate()
                    jobcachelock.write(processStatus)
                    jobcachelock.close()
                    output_callbacks(outputs, processStatus)

                output_callbacks = partial(
                    update_status_output_callback, output_callbacks, jobcachelock
                )

        builder = self._init_job(job_order, runtimeContext)

        reffiles = copy.deepcopy(builder.files)

        j = self.make_job_runner(runtimeContext)(
            builder,
            builder.job,
            self.make_path_mapper,
            self.requirements,
            self.hints,
            jobname,
        )
        j.prov_obj = self.prov_obj

        j.successCodes = self.tool.get("successCodes", [])
        j.temporaryFailCodes = self.tool.get("temporaryFailCodes", [])
        j.permanentFailCodes = self.tool.get("permanentFailCodes", [])

        debug = _logger.isEnabledFor(logging.DEBUG)

        if debug:
            _logger.debug(
                "[job %s] initializing from %s%s",
                j.name,
                self.tool.get("id", ""),
                " as part of %s" % runtimeContext.part_of
                if runtimeContext.part_of
                else "",
            )
            _logger.debug("[job %s] %s", j.name, json_dumps(builder.job, indent=4))

        builder.pathmapper = self.make_path_mapper(
            reffiles, builder.stagedir, runtimeContext, True
        )
        builder.requirements = j.requirements

        _check_adjust = partial(check_adjust, builder)

        visit_class(
            [builder.files, builder.bindings], ("File", "Directory"), _check_adjust
        )

        self._initialworkdir(j, builder)

        if debug:
            _logger.debug(
                "[job %s] path mappings is %s",
                j.name,
                json_dumps(
                    {
                        p: builder.pathmapper.mapper(p)
                        for p in builder.pathmapper.files()
                    },
                    indent=4,
                ),
            )

        if self.tool.get("stdin"):
            with SourceLine(self.tool, "stdin", ValidationException, debug):
                j.stdin = cast(str, builder.do_eval(self.tool["stdin"]))
                if j.stdin:
                    reffiles.append({"class": "File", "path": j.stdin})

        if self.tool.get("stderr"):
            with SourceLine(self.tool, "stderr", ValidationException, debug):
                j.stderr = cast(str, builder.do_eval(self.tool["stderr"]))
                if j.stderr:
                    if os.path.isabs(j.stderr) or ".." in j.stderr:
                        raise ValidationException(
                            "stderr must be a relative path, got '%s'" % j.stderr
                        )

        if self.tool.get("stdout"):
            with SourceLine(self.tool, "stdout", ValidationException, debug):
                j.stdout = cast(str, builder.do_eval(self.tool["stdout"]))
                if j.stdout:
                    if os.path.isabs(j.stdout) or ".." in j.stdout or not j.stdout:
                        raise ValidationException(
                            "stdout must be a relative path, got '%s'" % j.stdout
                        )

        if debug:
            _logger.debug(
                "[job %s] command line bindings is %s",
                j.name,
                json_dumps(builder.bindings, indent=4),
            )
        dockerReq, _ = self.get_requirement("DockerRequirement")
        if dockerReq is not None and runtimeContext.use_container:
            j.outdir = runtimeContext.get_outdir()
            j.tmpdir = runtimeContext.get_tmpdir()
            j.stagedir = runtimeContext.create_tmpdir()
        else:
            j.outdir = builder.outdir
            j.tmpdir = builder.tmpdir
            j.stagedir = builder.stagedir

        inplaceUpdateReq, _ = self.get_requirement("InplaceUpdateRequirement")
        if inplaceUpdateReq is not None:
            j.inplace_update = cast(bool, inplaceUpdateReq["inplaceUpdate"])
        normalizeFilesDirs(j.generatefiles)

        readers = {}  # type: Dict[str, CWLObjectType]
        muts = set()  # type: Set[str]

        if builder.mutation_manager is not None:

            def register_mut(f: CWLObjectType) -> None:
                mm = cast(MutationManager, builder.mutation_manager)
                muts.add(cast(str, f["location"]))
                mm.register_mutation(j.name, f)

            def register_reader(f: CWLObjectType) -> None:
                mm = cast(MutationManager, builder.mutation_manager)
                if cast(str, f["location"]) not in muts:
                    mm.register_reader(j.name, f)
                    readers[cast(str, f["location"])] = copy.deepcopy(f)

            for li in j.generatefiles["listing"]:
                if li.get("writable") and j.inplace_update:
                    adjustFileObjs(li, register_mut)
                    adjustDirObjs(li, register_mut)
                else:
                    adjustFileObjs(li, register_reader)
                    adjustDirObjs(li, register_reader)

            adjustFileObjs(builder.files, register_reader)
            adjustFileObjs(builder.bindings, register_reader)
            adjustDirObjs(builder.files, register_reader)
            adjustDirObjs(builder.bindings, register_reader)

        timelimit, _ = self.get_requirement("ToolTimeLimit")
        if timelimit is not None:
            with SourceLine(timelimit, "timelimit", ValidationException, debug):
                j.timelimit = cast(
                    Optional[int],
                    builder.do_eval(cast(Union[int, str], timelimit["timelimit"])),
                )
                if not isinstance(j.timelimit, int) or j.timelimit < 0:
                    raise WorkflowException(
                        "timelimit must be an integer >= 0, got: %s" % j.timelimit
                    )

        networkaccess, _ = self.get_requirement("NetworkAccess")
        if networkaccess is not None:
            with SourceLine(networkaccess, "networkAccess", ValidationException, debug):
                j.networkaccess = cast(
                    bool,
                    builder.do_eval(
                        cast(Union[bool, str], networkaccess["networkAccess"])
                    ),
                )
                if not isinstance(j.networkaccess, bool):
                    raise WorkflowException(
                        "networkAccess must be a boolean, got: %s" % j.networkaccess
                    )

        j.environment = {}
        evr, _ = self.get_requirement("EnvVarRequirement")
        if evr is not None:
            for t3 in cast(List[Dict[str, str]], evr["envDef"]):
                j.environment[t3["envName"]] = cast(
                    str, builder.do_eval(t3["envValue"])
                )

        shellcmd, _ = self.get_requirement("ShellCommandRequirement")
        if shellcmd is not None:
            cmd = []  # type: List[str]
            for b in builder.bindings:
                arg = builder.generate_arg(b)
                if b.get("shellQuote", True):
                    arg = [shellescape.quote(a) for a in aslist(arg)]
                cmd.extend(aslist(arg))
            j.command_line = ["/bin/sh", "-c", " ".join(cmd)]
        else:
            j.command_line = flatten(list(map(builder.generate_arg, builder.bindings)))

        j.pathmapper = builder.pathmapper
        j.collect_outputs = partial(
            self.collect_output_ports,
            self.tool["outputs"],
            builder,
            compute_checksum=getdefault(runtimeContext.compute_checksum, True),
            jobname=jobname,
            readers=readers,
        )
        j.output_callback = output_callbacks

        mpi, _ = self.get_requirement(MPIRequirementName)

        if mpi is not None:
            np = cast(  # From the schema for MPIRequirement.processes
                Union[int, str],
                mpi.get("processes", runtimeContext.mpi_config.default_nproc),
            )
            if isinstance(np, str):
                tmp = builder.do_eval(np)
                if not isinstance(tmp, int):
                    raise TypeError(
                        "{} needs 'processes' to evaluate to an int, got {}".format(
                            MPIRequirementName, type(np)
                        )
                    )
                np = tmp
            j.mpi_procs = np
        yield j

    def collect_output_ports(
        self,
        ports: Union[CommentedSeq, Set[CWLObjectType]],
        builder: Builder,
        outdir: str,
        rcode: int,
        compute_checksum: bool = True,
        jobname: str = "",
        readers: Optional[MutableMapping[str, CWLObjectType]] = None,
    ) -> OutputPortsType:
        ret = {}  # type: OutputPortsType
        debug = _logger.isEnabledFor(logging.DEBUG)
        cwl_version = self.metadata.get(
            "http://commonwl.org/cwltool#original_cwlVersion", None
        )
        if cwl_version != "v1.0":
            builder.resources["exitCode"] = rcode
        try:
            fs_access = builder.make_fs_access(outdir)
            custom_output = fs_access.join(outdir, "cwl.output.json")
            if fs_access.exists(custom_output):
                with fs_access.open(custom_output, "r") as f:
                    ret = json.load(f)
                if debug:
                    _logger.debug(
                        "Raw output from %s: %s",
                        custom_output,
                        json_dumps(ret, indent=4),
                    )
            else:
                for i, port in enumerate(ports):

                    with SourceLine(
                        ports,
                        i,
                        partial(ParameterOutputWorkflowException, port=port),
                        debug,
                    ):
                        fragment = shortname(port["id"])
                        ret[fragment] = self.collect_output(
                            port,
                            builder,
                            outdir,
                            fs_access,
                            compute_checksum=compute_checksum,
                        )
            if ret:
                revmap = partial(revmap_file, builder, outdir)
                adjustDirObjs(ret, trim_listing)
                visit_class(ret, ("File", "Directory"), revmap)
                visit_class(ret, ("File", "Directory"), remove_path)
                normalizeFilesDirs(ret)
                visit_class(
                    ret,
                    ("File", "Directory"),
                    partial(check_valid_locations, fs_access),
                )

                if compute_checksum:
                    adjustFileObjs(ret, partial(compute_checksums, fs_access))
            expected_schema = cast(
                Schema, self.names.get_name("outputs_record_schema", None)
            )
            validate_ex(
                expected_schema, ret, strict=False, logger=_logger_validation_warnings
            )
            if ret is not None and builder.mutation_manager is not None:
                adjustFileObjs(ret, builder.mutation_manager.set_generation)
            return ret if ret is not None else {}
        except ValidationException as e:
            raise WorkflowException(
                "Error validating output record. "
                + str(e)
                + "\n in "
                + json_dumps(ret, indent=4)
            ) from e
        finally:
            if builder.mutation_manager and readers:
                for r in readers.values():
                    builder.mutation_manager.release_reader(jobname, r)

    def collect_output(
        self,
        schema: CWLObjectType,
        builder: Builder,
        outdir: str,
        fs_access: StdFsAccess,
        compute_checksum: bool = True,
    ) -> Optional[CWLOutputType]:
        r = []  # type: List[CWLOutputType]
        empty_and_optional = False
        debug = _logger.isEnabledFor(logging.DEBUG)
        result: Optional[CWLOutputType] = None
        if "outputBinding" in schema:
            binding = cast(
                MutableMapping[str, Union[bool, str, List[str]]],
                schema["outputBinding"],
            )
            globpatterns = []  # type: List[str]

            revmap = partial(revmap_file, builder, outdir)

            if "glob" in binding:
                with SourceLine(binding, "glob", WorkflowException, debug):
                    for gb in aslist(binding["glob"]):
                        gb = builder.do_eval(gb)
                        if gb:
                            globpatterns.extend(aslist(gb))

                    for gb in globpatterns:
                        if gb.startswith(builder.outdir):
                            gb = gb[len(builder.outdir) + 1 :]
                        elif gb == ".":
                            gb = outdir
                        elif gb.startswith("/"):
                            raise WorkflowException(
                                "glob patterns must not start with '/'"
                            )
                        try:
                            prefix = fs_access.glob(outdir)
                            r.extend(
                                [
                                    {
                                        "location": g,
                                        "path": fs_access.join(
                                            builder.outdir, g[len(prefix[0]) + 1 :]
                                        ),
                                        "basename": os.path.basename(g),
                                        "nameroot": os.path.splitext(
                                            os.path.basename(g)
                                        )[0],
                                        "nameext": os.path.splitext(
                                            os.path.basename(g)
                                        )[1],
                                        "class": "File"
                                        if fs_access.isfile(g)
                                        else "Directory",
                                    }
                                    for g in sorted(
                                        fs_access.glob(fs_access.join(outdir, gb)),
                                        key=cmp_to_key(
                                            cast(
                                                Callable[[str, str], int],
                                                locale.strcoll,
                                            )
                                        ),
                                    )
                                ]
                            )
                        except (OSError) as e:
                            _logger.warning(str(e))
                        except Exception:
                            _logger.error(
                                "Unexpected error from fs_access", exc_info=True
                            )
                            raise

                for files in cast(List[Dict[str, Optional[CWLOutputType]]], r):
                    rfile = files.copy()
                    revmap(rfile)
                    if files["class"] == "Directory":
                        ll = binding.get("loadListing") or builder.loadListing
                        if ll and ll != "no_listing":
                            get_listing(fs_access, files, (ll == "deep_listing"))
                    else:
                        if binding.get("loadContents"):
                            with fs_access.open(
                                cast(str, rfile["location"]), "rb"
                            ) as f:
                                files["contents"] = content_limit_respected_read_bytes(
                                    f
                                ).decode("utf-8")
                        if compute_checksum:
                            with fs_access.open(
                                cast(str, rfile["location"]), "rb"
                            ) as f:
                                checksum = hashlib.sha1()  # nosec
                                contents = f.read(1024 * 1024)
                                while contents != b"":
                                    checksum.update(contents)
                                    contents = f.read(1024 * 1024)
                                files["checksum"] = "sha1$%s" % checksum.hexdigest()
                        files["size"] = fs_access.size(cast(str, rfile["location"]))

            optional = False
            single = False
            if isinstance(schema["type"], MutableSequence):
                if "null" in schema["type"]:
                    optional = True
                if "File" in schema["type"] or "Directory" in schema["type"]:
                    single = True
            elif schema["type"] == "File" or schema["type"] == "Directory":
                single = True

            if "outputEval" in binding:
                with SourceLine(binding, "outputEval", WorkflowException, debug):
                    result = builder.do_eval(
                        cast(CWLOutputType, binding["outputEval"]), context=r
                    )
            else:
                result = cast(CWLOutputType, r)

            if single:
                if not result and not optional:
                    with SourceLine(binding, "glob", WorkflowException, debug):
                        raise WorkflowException(
                            "Did not find output file with glob pattern: '{}'".format(
                                globpatterns
                            )
                        )
                elif not result and optional:
                    pass
                elif isinstance(result, MutableSequence):
                    if len(result) > 1:
                        raise WorkflowException(
                            "Multiple matches for output item that is a single file."
                        )
                    else:
                        result = cast(CWLOutputType, result[0])

            if "secondaryFiles" in schema:
                with SourceLine(schema, "secondaryFiles", WorkflowException, debug):
                    for primary in aslist(result):
                        if isinstance(primary, MutableMapping):
                            primary.setdefault("secondaryFiles", [])
                            pathprefix = primary["path"][
                                0 : primary["path"].rindex(os.sep) + 1
                            ]
                            for sf in aslist(schema["secondaryFiles"]):
                                if "required" in sf:
                                    sf_required = builder.do_eval(
                                        sf["required"], context=primary
                                    )
                                else:
                                    sf_required = False

                                if "$(" in sf["pattern"] or "${" in sf["pattern"]:
                                    sfpath = builder.do_eval(
                                        sf["pattern"], context=primary
                                    )
                                else:
                                    sfpath = substitute(
                                        primary["basename"], sf["pattern"]
                                    )

                                for sfitem in aslist(sfpath):
                                    if not sfitem:
                                        continue
                                    if isinstance(sfitem, str):
                                        sfitem = {"path": pathprefix + sfitem}
                                    if (
                                        not fs_access.exists(sfitem["path"])
                                        and sf_required
                                    ):
                                        raise WorkflowException(
                                            "Missing required secondary file '%s'"
                                            % (sfitem["path"])
                                        )
                                    if "path" in sfitem and "location" not in sfitem:
                                        revmap(sfitem)
                                    if fs_access.isfile(sfitem["location"]):
                                        sfitem["class"] = "File"
                                        primary["secondaryFiles"].append(sfitem)
                                    elif fs_access.isdir(sfitem["location"]):
                                        sfitem["class"] = "Directory"
                                        primary["secondaryFiles"].append(sfitem)

            if "format" in schema:
                for primary in aslist(result):
                    primary["format"] = builder.do_eval(
                        schema["format"], context=primary
                    )

            # Ensure files point to local references outside of the run environment
            adjustFileObjs(result, revmap)

            if not result and optional:
                # Don't convert zero or empty string to None
                if result in [0, ""]:
                    return result
                # For [] or None, return None
                else:
                    return None

        if (
            not empty_and_optional
            and isinstance(schema["type"], MutableMapping)
            and schema["type"]["type"] == "record"
        ):
            out = {}
            for field in cast(List[CWLObjectType], schema["type"]["fields"]):
                out[shortname(cast(str, field["name"]))] = self.collect_output(
                    field, builder, outdir, fs_access, compute_checksum=compute_checksum
                )
            return out
        return result
