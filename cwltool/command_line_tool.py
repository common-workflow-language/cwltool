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
import urllib.parse
from enum import Enum
from functools import cmp_to_key, partial
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Pattern,
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

from .builder import (
    INPUT_OBJ_VOCAB,
    Builder,
    content_limit_respected_read_bytes,
    substitute,
)
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
from .update import ORDERED_VERSIONS, ORIGINAL_CWLVERSION
from .utils import (
    CWLObjectType,
    CWLOutputType,
    DirectoryType,
    JobsGeneratorType,
    OutputCallbackType,
    adjustDirObjs,
    adjustFileObjs,
    aslist,
    get_listing,
    normalizeFilesDirs,
    random_outdir,
    shared_file_lock,
    trim_listing,
    upgrade_lock,
    visit_class,
)

if TYPE_CHECKING:
    from .provenance_profile import ProvenanceProfile  # pylint: disable=unused-import


class PathCheckingMode(Enum):
    """
    What characters are allowed in path names.

    We have the strict (default) mode and the relaxed mode.
    """

    STRICT = re.compile(r"^[\w.+\,\-:@\]^\u2600-\u26FF\U0001f600-\U0001f64f]+$")
    # accepts names that contain one or more of the following:
    # "\w"                  unicode word characters; this includes most characters
    #                            that can be part of a word in any language, as well
    #                            as numbers and the underscore
    # "."                    a literal period
    # "+"                    a literal plus sign
    # "\,"                  a literal comma
    # "\-"                  a literal minus sign
    # ":"                    a literal colon
    # "@"                    a literal at-symbol
    # "\]"                  a literal end-square-bracket
    # "^"                    a literal caret symbol
    # \u2600-\u26FF                  matches a single character in the range between
    #                       ☀ (index 9728) and ⛿ (index 9983)
    # \U0001f600-\U0001f64f matches a single character in the range between
    #                       😀 (index 128512) and 🙏 (index 128591)

    # Note: the following characters are intentionally not included:
    #
    # 1. reserved words in POSIX:
    # ! { }
    #
    # 2. POSIX metacharacters listed in the CWL standard as okay to reject
    # | & ; < > ( ) $ ` " ' <space> <tab> <newline>
    # (In accordance with
    # https://www.commonwl.org/v1.0/CommandLineTool.html#File under "path" )
    #
    # 3. POSIX path separator
    # \
    # (also listed at
    # https://www.commonwl.org/v1.0/CommandLineTool.html#File under "path")
    #
    # 4. Additional POSIX metacharacters
    # * ? [ # ˜ = %

    # TODO: switch to https://pypi.org/project/regex/ and use
    # `\p{Extended_Pictographic}` instead of the manual emoji ranges

    RELAXED = re.compile(r".*")  # Accept anything


class ExpressionJob:
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

    # builder.outdir is the inner (container/compute node) output directory
    # outdir is the outer (host/storage system) output directory

    if outdir.startswith("/"):
        # local file path, turn it into a file:// URI
        outdir = file_uri(outdir)

    # note: outer outdir should already be a URI and should not be URI
    # quoted any further.

    if "location" in f and "path" not in f:
        location = cast(str, f["location"])
        if location.startswith("file://"):
            f["path"] = uri_file_path(location)
        else:
            f["location"] = builder.fs_access.join(outdir, cast(str, f["location"]))
            return f

    if "dirname" in f:
        del f["dirname"]

    if "path" in f:
        path = builder.fs_access.join(builder.outdir, cast(str, f["path"]))
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
            f["location"] = uripath
        elif (
            path == builder.outdir
            or path.startswith(builder.outdir + os.sep)
            or path.startswith(builder.outdir + "/")
        ):
            joined_path = builder.fs_access.join(
                outdir, urllib.parse.quote(path[len(builder.outdir) + 1 :])
            )
            f["location"] = joined_path
        else:
            raise WorkflowException(
                "Output file path %s must be within designated output directory (%s) or an input "
                "file pass through." % (path, builder.outdir)
            )
        return f

    raise WorkflowException(
        "Output File object is missing both 'location' and 'path' fields: %s" % f
    )


class CallbackJob:
    """Callback Job class, used by CommandLine.job()."""

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


def check_adjust(
    accept_re: Pattern[str], builder: Builder, file_o: CWLObjectType
) -> CWLObjectType:
    """
    Map files to assigned path inside a container.

    We need to also explicitly walk over input, as implicit reassignment
    doesn't reach everything in builder.bindings
    """
    if not builder.pathmapper:
        raise ValueError(
            "Do not call check_adjust using a builder that doesn't have a pathmapper."
        )
    file_o["path"] = path = builder.pathmapper.mapper(cast(str, file_o["location"]))[1]
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
    if not accept_re.match(basename):
        raise WorkflowException(
            f"Invalid filename: '{file_o['basename']}' contains illegal characters"
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
        super().__init__(
            "Error collecting output for parameter '%s': %s"
            % (shortname(cast(str, port["id"])), msg),
            kwargs,
        )


class CommandLineTool(Process):
    def __init__(
        self, toolpath_object: CommentedMap, loadingContext: LoadingContext
    ) -> None:
        """Initialize this CommandLineTool."""
        super().__init__(toolpath_object, loadingContext)
        self.prov_obj = loadingContext.prov_obj
        self.path_check_mode = (
            PathCheckingMode.RELAXED
            if loadingContext.relax_path_checks
            else PathCheckingMode.STRICT
        )  # type: PathCheckingMode

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
        debug = _logger.isEnabledFor(logging.DEBUG)
        cwl_version = cast(Optional[str], self.metadata.get(ORIGINAL_CWLVERSION, None))
        classic_dirent: bool = cwl_version is not None and (
            ORDERED_VERSIONS.index(cwl_version) < ORDERED_VERSIONS.index("v1.2.0-dev2")
        )
        classic_listing = cwl_version and ORDERED_VERSIONS.index(
            cwl_version
        ) < ORDERED_VERSIONS.index("v1.1.0-dev1")

        ls = []  # type: List[CWLObjectType]
        if isinstance(initialWorkdir["listing"], str):
            # "listing" is just a string (must be an expression) so
            # just evaluate it and use the result as if it was in
            # listing
            ls_evaluated = builder.do_eval(initialWorkdir["listing"])
            fail: Any = False
            fail_suffix: str = ""
            if not isinstance(ls_evaluated, MutableSequence):
                fail = ls_evaluated
            else:
                ls_evaluated2 = cast(
                    MutableSequence[Union[None, CWLOutputType]], ls_evaluated
                )
                for entry in ls_evaluated2:
                    if entry == None:  # noqa
                        if classic_dirent:
                            fail = entry
                            fail_suffix = (
                                " Dirent.entry cannot return 'null' before CWL "
                                "v1.2. Please consider using 'cwl-upgrader' to "
                                "upgrade your document to CWL version v1.2."
                            )
                    elif isinstance(entry, MutableSequence):
                        if classic_listing:
                            raise SourceLine(
                                initialWorkdir, "listing", WorkflowException, debug
                            ).makeError(
                                "InitialWorkDirRequirement.listing expressions "
                                "cannot return arrays of Files or Directories "
                                "before CWL v1.1. Please "
                                "considering using 'cwl-upgrader' to upgrade "
                                "your document to CWL v1.1' or later."
                            )
                        else:
                            for entry2 in entry:
                                if not (
                                    isinstance(entry2, MutableMapping)
                                    and (
                                        "class" in entry2
                                        and entry2["class"] == "File"
                                        or "Directory"
                                    )
                                ):
                                    fail = (
                                        "an array with an item ('{entry2}') that is "
                                        "not a File nor a Directory object."
                                    )
                    elif not (
                        isinstance(entry, MutableMapping)
                        and (
                            "class" in entry
                            and (entry["class"] == "File" or "Directory")
                            or "entry" in entry
                        )
                    ):
                        fail = entry
            if fail is not False:
                message = (
                    "Expression in a 'InitialWorkdirRequirement.listing' field "
                    "must return a list containing zero or more of: File or "
                    "Directory objects; Dirent objects"
                )
                if classic_dirent:
                    message += ". "
                else:
                    message += "; null; or arrays of File or Directory objects. "
                message += f"Got '{fail}' among the results from "
                message += f"'{initialWorkdir['listing'].strip()}'." + fail_suffix
                raise SourceLine(
                    initialWorkdir, "listing", WorkflowException, debug
                ).makeError(message)
            ls = cast(List[CWLObjectType], ls_evaluated)
        else:
            # "listing" is an array of either expressions or Dirent so
            # evaluate each item
            for t in cast(
                MutableSequence[Union[str, CWLObjectType]],
                initialWorkdir["listing"],
            ):
                if isinstance(t, Mapping) and "entry" in t:
                    # Dirent
                    entry_field = cast(str, t["entry"])
                    # the schema guarantees that 'entry' is a string, so the cast is safe
                    entry = builder.do_eval(entry_field, strip_whitespace=False)
                    if entry is None:
                        continue

                    if isinstance(entry, MutableSequence):
                        if classic_listing:
                            raise SourceLine(
                                t, "entry", WorkflowException, debug
                            ).makeError(
                                "'entry' expressions are not allowed to evaluate "
                                "to an array of Files or Directories until CWL "
                                "v1.2. Consider using 'cwl-upgrader' to upgrade "
                                "your document to CWL version 1.2."
                            )
                        # Nested list.  If it is a list of File or
                        # Directory objects, add it to the
                        # file list, otherwise JSON serialize it if CWL v1.2.

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
                                    t, "entryname", WorkflowException, debug
                                ).makeError(
                                    "'entryname' is invalid when 'entry' returns list of File or Directory"
                                )
                            for e in entry:
                                ec = cast(CWLObjectType, e)
                                ec["writable"] = t.get("writable", False)
                            ls.extend(cast(List[CWLObjectType], entry))
                            continue

                    et = {}  # type: CWLObjectType
                    if isinstance(entry, Mapping) and entry.get("class") in (
                        "File",
                        "Directory",
                    ):
                        et["entry"] = cast(CWLOutputType, entry)
                    else:
                        if isinstance(entry, str):
                            et["entry"] = entry
                        else:
                            if classic_dirent:
                                raise SourceLine(
                                    t, "entry", WorkflowException, debug
                                ).makeError(
                                    "'entry' expression resulted in "
                                    "something other than number, object or "
                                    "array besides a single File or Dirent object. "
                                    "In CWL v1.2+ this would be serialized to a JSON object. "
                                    "However this is a {cwl_version} document. "
                                    "If that is the desired result then please "
                                    "consider using 'cwl-upgrader' to upgrade "
                                    "your document to CWL version 1.2. "
                                    f"Result of '{entry_field}' was '{entry}'."
                                )
                            et["entry"] = json_dumps(entry, sort_keys=True)

                    if "entryname" in t:
                        entryname_field = cast(str, t["entryname"])
                        if "${" in entryname_field or "$(" in entryname_field:
                            en = builder.do_eval(cast(str, t["entryname"]))
                            if not isinstance(en, str):
                                raise SourceLine(
                                    t, "entryname", WorkflowException, debug
                                ).makeError(
                                    "'entryname' expression must result a string. "
                                    f"Got '{en}' from '{entryname_field}'"
                                )
                            et["entryname"] = en
                        else:
                            et["entryname"] = entryname_field
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
                    initialWorkdir, "listing", WorkflowException, debug
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
                        initialWorkdir, "listing", WorkflowException, debug
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
                    initialWorkdir, "listing", WorkflowException, debug
                ).makeError(
                    "Entry at index %s of listing is not a record, was %s"
                    % (i, type(t2["entry"]))
                )

            if t2["entry"].get("class") not in ("File", "Directory"):
                raise SourceLine(
                    initialWorkdir, "listing", WorkflowException, debug
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
                    initialWorkdir, "listing", WorkflowException, debug
                ).makeError(
                    f"Entry at index {i} of listing is not a Dirent, File or "
                    f"Directory object, was {t2}."
                )
            if "basename" not in t3:
                continue
            basename = os.path.normpath(cast(str, t3["basename"]))
            t3["basename"] = basename
            if basename.startswith("../"):
                raise SourceLine(
                    initialWorkdir, "listing", WorkflowException, debug
                ).makeError(
                    f"Name '{basename}' at index {i} of listing is invalid, "
                    "cannot start with '../'"
                )
            if basename.startswith("/"):
                # only if DockerRequirement in requirements
                if cwl_version and ORDERED_VERSIONS.index(
                    cwl_version
                ) < ORDERED_VERSIONS.index("v1.2.0-dev4"):
                    raise SourceLine(
                        initialWorkdir, "listing", WorkflowException, debug
                    ).makeError(
                        f"Name '{basename}' at index {i} of listing is invalid, "
                        "paths starting with '/' are only permitted in CWL 1.2 "
                        "and later. Consider changing the absolute path to a relative "
                        "path, or upgrade the CWL description to CWL v1.2 using "
                        "https://pypi.org/project/cwl-upgrader/"
                    )

                req, is_req = self.get_requirement("DockerRequirement")
                if is_req is not True:
                    raise SourceLine(
                        initialWorkdir, "listing", WorkflowException, debug
                    ).makeError(
                        f"Name '{basename}' at index {i} of listing is invalid, "
                        "name can only start with '/' when DockerRequirement "
                        "is in 'requirements'."
                    )

        with SourceLine(initialWorkdir, "listing", WorkflowException, debug):
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
                partial(check_adjust, self.path_check_mode.value, builder),
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
            _check_adjust = partial(
                check_adjust, self.path_check_mode.value, cachebuilder
            )
            _checksum = partial(
                compute_checksums,
                runtimeContext.make_fs_access(runtimeContext.basedir),
            )
            visit_class(
                [cachebuilder.files, cachebuilder.bindings],
                ("File", "Directory"),
                _check_adjust,
            )
            visit_class(
                [cachebuilder.files, cachebuilder.bindings], ("File"), _checksum
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

            def remove_prefix(s: str, prefix: str) -> str:
                # replace with str.removeprefix when Python 3.9+
                return s[len(prefix) :] if s.startswith(prefix) else s

            for location, fobj in cachebuilder.pathmapper.items():
                if fobj.type == "File":
                    checksum = calc_checksum(location)
                    fobj_stat = os.stat(fobj.resolved)
                    path = remove_prefix(fobj.resolved, runtimeContext.basedir + "/")
                    if checksum is not None:
                        keydict[path] = [fobj_stat.st_size, checksum]
                    else:
                        keydict[path] = [
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
            jobcachepending = f"{jobcache}.status"
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

        _check_adjust = partial(check_adjust, self.path_check_mode.value, builder)

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
                stdin_eval = builder.do_eval(self.tool["stdin"])
                if not (isinstance(stdin_eval, str) or stdin_eval is None):
                    raise ValidationException(
                        f"'stdin' expression must return a string or null. Got '{stdin_eval}' "
                        f"for '{self.tool['stdin']}'."
                    )
                j.stdin = stdin_eval
                if j.stdin:
                    reffiles.append({"class": "File", "path": j.stdin})

        if self.tool.get("stderr"):
            with SourceLine(self.tool, "stderr", ValidationException, debug):
                stderr_eval = builder.do_eval(self.tool["stderr"])
                if not isinstance(stderr_eval, str):
                    raise ValidationException(
                        f"'stderr' expression must return a string. Got '{stderr_eval}' "
                        f"for '{self.tool['stderr']}'."
                    )
                j.stderr = stderr_eval
                if j.stderr:
                    if os.path.isabs(j.stderr) or ".." in j.stderr:
                        raise ValidationException(
                            "stderr must be a relative path, got '%s'" % j.stderr
                        )

        if self.tool.get("stdout"):
            with SourceLine(self.tool, "stdout", ValidationException, debug):
                stdout_eval = builder.do_eval(self.tool["stdout"])
                if not isinstance(stdout_eval, str):
                    raise ValidationException(
                        f"'stdout' expression must return a string. Got '{stdout_eval}' "
                        f"for '{self.tool['stdout']}'."
                    )
                j.stdout = stdout_eval
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
                limit_field = cast(Dict[str, Union[str, int]], timelimit)["timelimit"]
                if isinstance(limit_field, str):
                    timelimit_eval = builder.do_eval(limit_field)
                    if timelimit_eval and not isinstance(timelimit_eval, int):
                        raise WorkflowException(
                            "'timelimit' expression must evaluate to a long/int. Got "
                            f"'{timelimit_eval}' for expression '{limit_field}'."
                        )
                else:
                    timelimit_eval = limit_field
                if not isinstance(timelimit_eval, int) or timelimit_eval < 0:
                    raise WorkflowException(
                        f"timelimit must be an integer >= 0, got: {timelimit_eval}"
                    )
                j.timelimit = timelimit_eval

        networkaccess, _ = self.get_requirement("NetworkAccess")
        if networkaccess is not None:
            with SourceLine(networkaccess, "networkAccess", ValidationException, debug):
                networkaccess_field = networkaccess["networkAccess"]
                if isinstance(networkaccess_field, str):
                    networkaccess_eval = builder.do_eval(networkaccess_field)
                    if not isinstance(networkaccess_eval, bool):
                        raise WorkflowException(
                            "'networkAccess' expression must evaluate to a bool. "
                            f"Got '{networkaccess_eval}' for expression '{networkaccess_field}'."
                        )
                else:
                    networkaccess_eval = networkaccess_field
                if not isinstance(networkaccess_eval, bool):
                    raise WorkflowException(
                        "networkAccess must be a boolean, got: {networkaccess_eval}."
                    )
                j.networkaccess = networkaccess_eval

        # Build a mapping to hold any EnvVarRequirement
        required_env = {}
        evr, _ = self.get_requirement("EnvVarRequirement")
        if evr is not None:
            for eindex, t3 in enumerate(cast(List[Dict[str, str]], evr["envDef"])):
                env_value_field = t3["envValue"]
                if "${" in env_value_field or "$(" in env_value_field:
                    env_value_eval = builder.do_eval(env_value_field)
                    if not isinstance(env_value_eval, str):
                        raise SourceLine(
                            evr["envDef"], eindex, WorkflowException, debug
                        ).makeError(
                            "'envValue expression must evaluate to a str. "
                            f"Got '{env_value_eval}' for expression '{env_value_field}'."
                        )
                    env_value = env_value_eval
                else:
                    env_value = env_value_field
                required_env[t3["envName"]] = env_value
        # Construct the env
        j.prepare_environment(runtimeContext, required_env)

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
                np_eval = builder.do_eval(np)
                if not isinstance(np_eval, int):
                    raise SourceLine(
                        mpi, "processes", WorkflowException, debug
                    ).makeError(
                        f"{MPIRequirementName} needs 'processes' expression to "
                        f"evaluate to an int, got '{np_eval}' for expression '{np}'."
                    )
                np = np_eval
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
        cwl_version = self.metadata.get(ORIGINAL_CWLVERSION, None)
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
                expected_schema,
                ret,
                strict=False,
                logger=_logger_validation_warnings,
                vocab=INPUT_OBJ_VOCAB,
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
                            gb_eval_fail = False
                            if not isinstance(gb, str):
                                if isinstance(gb, list):
                                    for entry in gb:
                                        if not isinstance(entry, str):
                                            gb_eval_fail = True
                                else:
                                    gb_eval_fail = True
                            if gb_eval_fail:
                                raise WorkflowException(
                                    "Resolved glob patterns must be strings "
                                    f"or list of strings, not "
                                    f"'{gb}' from '{binding['glob']}'"
                                )
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
                            sorted_glob_result = sorted(
                                fs_access.glob(fs_access.join(outdir, gb)),
                                key=cmp_to_key(locale.strcoll),
                            )
                            r.extend(
                                [
                                    {
                                        "location": g,
                                        "path": fs_access.join(
                                            builder.outdir,
                                            urllib.parse.unquote(
                                                g[len(prefix[0]) + 1 :]
                                            ),
                                        ),
                                        "basename": decoded_basename,
                                        "nameroot": os.path.splitext(decoded_basename)[
                                            0
                                        ],
                                        "nameext": os.path.splitext(decoded_basename)[
                                            1
                                        ],
                                        "class": "File"
                                        if fs_access.isfile(g)
                                        else "Directory",
                                    }
                                    for g, decoded_basename in zip(
                                        sorted_glob_result,
                                        map(
                                            lambda x: os.path.basename(
                                                urllib.parse.unquote(x)
                                            ),
                                            sorted_glob_result,
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
                with SourceLine(binding, "glob", WorkflowException, debug):
                    if not result and not optional:
                        raise WorkflowException(
                            f"Did not find output file with glob pattern: '{globpatterns}'."
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
                                    with SourceLine(
                                        schema["secondaryFiles"],
                                        "required",
                                        WorkflowException,
                                        debug,
                                    ):
                                        sf_required_eval = builder.do_eval(
                                            sf["required"], context=primary
                                        )
                                        if not (
                                            isinstance(sf_required_eval, bool)
                                            or sf_required_eval is None
                                        ):
                                            raise WorkflowException(
                                                "Expressions in the field "
                                                "'required' must evaluate to a "
                                                "Boolean (true or false) or None. "
                                                f"Got '{sf_required_eval}' for "
                                                f"'{sf['required']}'."
                                            )
                                        sf_required: bool = sf_required_eval or False
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
                format_field = cast(str, schema["format"])
                if "$(" in format_field or "${" in format_field:
                    for index, primary in enumerate(aslist(result)):
                        format_eval = builder.do_eval(format_field, context=primary)
                        if not isinstance(format_eval, str):
                            message = (
                                f"'format' expression must evaluate to a string. "
                                f"Got '{format_eval}' from '{format_field}'."
                            )
                            if isinstance(result, list):
                                message += f" 'self' had the value of the index {index} result: '{primary}'."
                            raise SourceLine(
                                schema, "format", WorkflowException, debug
                            ).makeError(message)
                        primary["format"] = format_eval
                else:
                    for primary in aslist(result):
                        primary["format"] = format_field
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
            not result
            and not empty_and_optional
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
