"""Loads a CWL document."""

import copy
import hashlib
import logging
import os
import re
import urllib
import uuid
from typing import (
    Any,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Tuple,
    Union,
    cast,
)

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.exceptions import ValidationException
from schema_salad.ref_resolver import Loader, file_uri
from schema_salad.schema import validate_doc
from schema_salad.sourceline import SourceLine, cmap
from schema_salad.utils import (
    ContextType,
    FetcherCallableType,
    IdxResultType,
    ResolveType,
    json_dumps,
)

from . import CWL_CONTENT_TYPES, process, update
from .context import LoadingContext
from .errors import GraphTargetMissingException
from .loghandler import _logger
from .process import Process, get_schema, shortname
from .update import ALLUPDATES
from .utils import CWLObjectType, ResolverType, visit_class

jobloaderctx = {
    "cwl": "https://w3id.org/cwl/cwl#",
    "cwltool": "http://commonwl.org/cwltool#",
    "path": {"@type": "@id"},
    "location": {"@type": "@id"},
    "id": "@id",
}  # type: ContextType


overrides_ctx = {
    "overrideTarget": {"@type": "@id"},
    "cwltool": "http://commonwl.org/cwltool#",
    "http://commonwl.org/cwltool#overrides": {
        "@id": "cwltool:overrides",
        "mapSubject": "overrideTarget",
    },
    "requirements": {
        "@id": "https://w3id.org/cwl/cwl#requirements",
        "mapSubject": "class",
    },
}  # type: ContextType


def default_loader(
    fetcher_constructor: Optional[FetcherCallableType] = None,
    enable_dev: bool = False,
    doc_cache: bool = True,
) -> Loader:
    return Loader(
        jobloaderctx,
        fetcher_constructor=fetcher_constructor,
        allow_attachments=lambda r: enable_dev,
        doc_cache=doc_cache,
    )


def resolve_tool_uri(
    argsworkflow: str,
    resolver: Optional[ResolverType] = None,
    fetcher_constructor: Optional[FetcherCallableType] = None,
    document_loader: Optional[Loader] = None,
) -> Tuple[str, str]:

    uri = None  # type: Optional[str]
    split = urllib.parse.urlsplit(argsworkflow)
    # In case of Windows path, urlsplit misjudge Drive letters as scheme, here we are skipping that
    if split.scheme and split.scheme in ["http", "https", "file"]:
        uri = argsworkflow
    elif os.path.exists(os.path.abspath(argsworkflow)):
        uri = file_uri(str(os.path.abspath(argsworkflow)))
    elif resolver is not None:
        uri = resolver(
            document_loader or default_loader(fetcher_constructor), argsworkflow
        )

    if uri is None:
        raise ValidationException("Not found: '%s'" % argsworkflow)

    if argsworkflow != uri:
        _logger.info("Resolved '%s' to '%s'", argsworkflow, uri)

    fileuri = urllib.parse.urldefrag(uri)[0]
    return uri, fileuri


def fetch_document(
    argsworkflow: Union[str, CWLObjectType],
    loadingContext: Optional[LoadingContext] = None,
) -> Tuple[LoadingContext, CommentedMap, str]:
    """Retrieve a CWL document."""
    if loadingContext is None:
        loadingContext = LoadingContext()
        loadingContext.loader = default_loader()
    else:
        loadingContext = loadingContext.copy()
        if loadingContext.loader is None:
            loadingContext.loader = default_loader(
                loadingContext.fetcher_constructor,
                enable_dev=loadingContext.enable_dev,
                doc_cache=loadingContext.doc_cache,
            )

    if isinstance(argsworkflow, str):
        uri, fileuri = resolve_tool_uri(
            argsworkflow,
            resolver=loadingContext.resolver,
            document_loader=loadingContext.loader,
        )
        workflowobj = cast(
            CommentedMap,
            loadingContext.loader.fetch(fileuri, content_types=CWL_CONTENT_TYPES),
        )
        return loadingContext, workflowobj, uri
    if isinstance(argsworkflow, MutableMapping):
        uri = (
            cast(str, argsworkflow["id"])
            if argsworkflow.get("id")
            else "_:" + str(uuid.uuid4())
        )
        workflowobj = cast(
            CommentedMap, cmap(cast(Dict[str, Any], argsworkflow), fn=uri)
        )
        loadingContext.loader.idx[uri] = workflowobj
        return loadingContext, workflowobj, uri
    raise ValidationException("Must be URI or object: '%s'" % argsworkflow)


def _convert_stdstreams_to_files(
    workflowobj: Union[
        CWLObjectType, MutableSequence[Union[CWLObjectType, str, int]], str
    ]
) -> None:
    if isinstance(workflowobj, MutableMapping):
        if workflowobj.get("class") == "CommandLineTool":
            with SourceLine(
                workflowobj,
                "outputs",
                ValidationException,
                _logger.isEnabledFor(logging.DEBUG),
            ):
                outputs = workflowobj.get("outputs", [])
                if not isinstance(outputs, CommentedSeq):
                    raise ValidationException('"outputs" section is not ' "valid.")
                for out in cast(
                    MutableSequence[CWLObjectType], workflowobj.get("outputs", [])
                ):
                    if not isinstance(out, CommentedMap):
                        raise ValidationException(
                            f"Output '{out}' is not a valid OutputParameter."
                        )
                    for streamtype in ["stdout", "stderr"]:
                        if out.get("type") == streamtype:
                            if "outputBinding" in out:
                                raise ValidationException(
                                    "Not allowed to specify outputBinding when"
                                    " using %s shortcut." % streamtype
                                )
                            if streamtype in workflowobj:
                                filename = workflowobj[streamtype]
                            else:
                                filename = str(
                                    hashlib.sha1(  # nosec
                                        json_dumps(workflowobj, sort_keys=True).encode(
                                            "utf-8"
                                        )
                                    ).hexdigest()
                                )
                                workflowobj[streamtype] = filename
                            out["type"] = "File"
                            out["outputBinding"] = cmap({"glob": filename})
            for inp in cast(
                MutableSequence[CWLObjectType], workflowobj.get("inputs", [])
            ):
                if inp.get("type") == "stdin":
                    if "inputBinding" in inp:
                        raise ValidationException(
                            "Not allowed to specify inputBinding when"
                            " using stdin shortcut."
                        )
                    if "stdin" in workflowobj:
                        raise ValidationException(
                            "Not allowed to specify stdin path when"
                            " using stdin type shortcut."
                        )
                    else:
                        workflowobj["stdin"] = (
                            "$(inputs.%s.path)"
                            % cast(str, inp["id"]).rpartition("#")[2].split("/")[-1]
                        )
                        inp["type"] = "File"
        else:
            for entry in workflowobj.values():
                _convert_stdstreams_to_files(
                    cast(
                        Union[
                            CWLObjectType,
                            MutableSequence[Union[CWLObjectType, str, int]],
                            str,
                        ],
                        entry,
                    )
                )
    if isinstance(workflowobj, MutableSequence):
        for entry in workflowobj:
            _convert_stdstreams_to_files(
                cast(
                    Union[
                        CWLObjectType,
                        MutableSequence[Union[CWLObjectType, str, int]],
                        str,
                    ],
                    entry,
                )
            )


def _add_blank_ids(
    workflowobj: Union[CWLObjectType, MutableSequence[Union[CWLObjectType, str]]]
) -> None:
    if isinstance(workflowobj, MutableMapping):
        if (
            "run" in workflowobj
            and isinstance(workflowobj["run"], MutableMapping)
            and "id" not in workflowobj["run"]
            and "$import" not in workflowobj["run"]
        ):
            workflowobj["run"]["id"] = str(uuid.uuid4())
        for entry in workflowobj.values():
            _add_blank_ids(
                cast(
                    Union[CWLObjectType, MutableSequence[Union[CWLObjectType, str]]],
                    entry,
                )
            )
    if isinstance(workflowobj, MutableSequence):
        for entry in workflowobj:
            _add_blank_ids(
                cast(
                    Union[CWLObjectType, MutableSequence[Union[CWLObjectType, str]]],
                    entry,
                )
            )


def resolve_and_validate_document(
    loadingContext: LoadingContext,
    workflowobj: Union[CommentedMap, CommentedSeq],
    uri: str,
    preprocess_only: bool = False,
    skip_schemas: Optional[bool] = None,
) -> Tuple[LoadingContext, str]:
    """Validate a CWL document."""
    if not loadingContext.loader:
        raise ValueError("loadingContext must have a loader.")
    else:
        loader = loadingContext.loader
    loadingContext = loadingContext.copy()

    if not isinstance(workflowobj, MutableMapping):
        raise ValueError(
            "workflowjobj must be a dict, got '{}': {}".format(
                type(workflowobj), workflowobj
            )
        )

    jobobj = None
    if "cwl:tool" in workflowobj:
        jobobj, _ = loader.resolve_all(workflowobj, uri)
        uri = urllib.parse.urljoin(uri, workflowobj["https://w3id.org/cwl/cwl#tool"])
        del cast(Dict[str, Any], jobobj)["https://w3id.org/cwl/cwl#tool"]

        workflowobj = fetch_document(uri, loadingContext)[1]

    fileuri = urllib.parse.urldefrag(uri)[0]

    cwlVersion = loadingContext.metadata.get("cwlVersion")
    if not cwlVersion:
        cwlVersion = workflowobj.get("cwlVersion")
    if not cwlVersion and fileuri != uri:
        # The tool we're loading is a fragment of a bigger file.  Get
        # the document root element and look for cwlVersion there.
        metadata = cast(CWLObjectType, fetch_document(fileuri, loadingContext)[1])
        cwlVersion = cast(str, metadata.get("cwlVersion"))
    if not cwlVersion:
        raise ValidationException(
            "No cwlVersion found. "
            "Use the following syntax in your CWL document to declare "
            "the version: cwlVersion: <version>.\n"
            "Note: if this is a CWL draft-3 (pre v1.0) document then it "
            "will need to be upgraded first using https://pypi.org/project/cwl-upgrader/ . "
            "'sbg:draft-2' documents can be upgraded using "
            "https://pypi.org/project/sevenbridges-cwl-draft2-upgrader/ ."
        )

    if not isinstance(cwlVersion, str):
        with SourceLine(
            workflowobj, "cwlVersion", ValidationException, loadingContext.debug
        ):
            raise ValidationException(
                f"'cwlVersion' must be a string, got {type(cwlVersion)}"
            )
    # strip out version
    cwlVersion = re.sub(r"^(?:cwl:|https://w3id.org/cwl/cwl#)", "", cwlVersion)
    if cwlVersion not in list(ALLUPDATES):
        # print out all the Supported Versions of cwlVersion
        versions = []
        for version in list(ALLUPDATES):
            if "dev" in version:
                version += " (with --enable-dev flag only)"
            versions.append(version)
        versions.sort()
        raise ValidationException(
            "The CWL reference runner no longer supports pre CWL v1.0 "
            "documents. Supported versions are: "
            "\n{}".format("\n".join(versions))
        )

    if (
        isinstance(jobobj, CommentedMap)
        and "http://commonwl.org/cwltool#overrides" in jobobj
    ):
        loadingContext.overrides_list.extend(resolve_overrides(jobobj, uri, uri))
        del jobobj["http://commonwl.org/cwltool#overrides"]

    if (
        isinstance(jobobj, CommentedMap)
        and "https://w3id.org/cwl/cwl#requirements" in jobobj
    ):
        if cwlVersion not in ("v1.1.0-dev1", "v1.1"):
            raise ValidationException(
                "`cwl:requirements` in the input object is not part of CWL "
                "v1.0. You can adjust to use `cwltool:overrides` instead; or you "
                "can set the cwlVersion to v1.1 or greater."
            )
        loadingContext.overrides_list.append(
            {
                "overrideTarget": uri,
                "requirements": jobobj["https://w3id.org/cwl/cwl#requirements"],
            }
        )
        del jobobj["https://w3id.org/cwl/cwl#requirements"]

    (sch_document_loader, avsc_names) = process.get_schema(cwlVersion)[:2]

    if isinstance(avsc_names, Exception):
        raise avsc_names

    processobj = None  # type: Optional[ResolveType]
    document_loader = Loader(
        sch_document_loader.ctx,
        schemagraph=sch_document_loader.graph,
        idx=loader.idx,
        cache=sch_document_loader.cache,
        fetcher_constructor=loadingContext.fetcher_constructor,
        skip_schemas=skip_schemas,
        doc_cache=loadingContext.doc_cache,
    )

    if cwlVersion == "v1.0":
        _add_blank_ids(workflowobj)

    document_loader.resolve_all(workflowobj, fileuri)
    processobj, metadata = document_loader.resolve_ref(uri)
    if not isinstance(processobj, (CommentedMap, CommentedSeq)):
        raise ValidationException("Workflow must be a CommentedMap or CommentedSeq.")

    if not hasattr(processobj.lc, "filename"):
        processobj.lc.filename = fileuri

    if loadingContext.metadata:
        metadata = loadingContext.metadata

    # Make a shallow copy.  If we do a version update later, metadata
    # will be updated, we don't want to write through and change the
    # original object.
    metadata = copy.copy(metadata)

    if not isinstance(metadata, CommentedMap):
        raise ValidationException(
            "metadata must be a CommentedMap, was %s" % type(metadata)
        )

    if isinstance(processobj, CommentedMap):
        uri = processobj["id"]

    _convert_stdstreams_to_files(workflowobj)

    if isinstance(jobobj, CommentedMap):
        loadingContext.jobdefaults = jobobj

    loadingContext.loader = document_loader
    loadingContext.avsc_names = avsc_names
    loadingContext.metadata = metadata

    if preprocess_only:
        return loadingContext, uri

    if loadingContext.do_validate:
        validate_doc(avsc_names, processobj, document_loader, loadingContext.strict)

    # None means default behavior (do update)
    if loadingContext.do_update in (True, None):
        if "cwlVersion" not in metadata:
            metadata["cwlVersion"] = cwlVersion
        processobj = update.update(
            processobj, document_loader, fileuri, loadingContext.enable_dev, metadata
        )
        document_loader.idx[processobj["id"]] = processobj

        def update_index(pr: CommentedMap) -> None:
            if "id" in pr:
                document_loader.idx[pr["id"]] = pr

        visit_class(
            processobj, ("CommandLineTool", "Workflow", "ExpressionTool"), update_index
        )

    return loadingContext, uri


def make_tool(
    uri: Union[str, CommentedMap, CommentedSeq], loadingContext: LoadingContext
) -> Process:
    """Make a Python CWL object."""
    if loadingContext.loader is None:
        raise ValueError("loadingContext must have a loader")
    resolveduri, metadata = loadingContext.loader.resolve_ref(uri)

    processobj = None
    if isinstance(resolveduri, MutableSequence):
        for obj in resolveduri:
            if obj["id"].endswith("#main"):
                processobj = obj
                break
        if not processobj:
            raise GraphTargetMissingException(
                "Tool file contains graph of multiple objects, must specify "
                "one of #%s"
                % ", #".join(
                    urllib.parse.urldefrag(i["id"])[1] for i in resolveduri if "id" in i
                )
            )
    elif isinstance(resolveduri, MutableMapping):
        processobj = resolveduri
    else:
        raise Exception("Must resolve to list or dict")

    tool = loadingContext.construct_tool_object(processobj, loadingContext)

    if loadingContext.jobdefaults:
        jobobj = loadingContext.jobdefaults
        for inp in tool.tool["inputs"]:
            if shortname(inp["id"]) in jobobj:
                inp["default"] = jobobj[shortname(inp["id"])]

    return tool


def load_tool(
    argsworkflow: Union[str, CWLObjectType],
    loadingContext: Optional[LoadingContext] = None,
) -> Process:

    loadingContext, workflowobj, uri = fetch_document(argsworkflow, loadingContext)

    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri
    )

    return make_tool(uri, loadingContext)


def resolve_overrides(
    ov: IdxResultType,
    ov_uri: str,
    baseurl: str,
) -> List[CWLObjectType]:
    ovloader = Loader(overrides_ctx)
    ret, _ = ovloader.resolve_all(ov, baseurl)
    if not isinstance(ret, CommentedMap):
        raise Exception("Expected CommentedMap, got %s" % type(ret))
    cwl_docloader = get_schema("v1.0")[0]
    cwl_docloader.resolve_all(ret, ov_uri)
    return cast(List[CWLObjectType], ret["http://commonwl.org/cwltool#overrides"])


def load_overrides(ov: str, base_url: str) -> List[CWLObjectType]:
    ovloader = Loader(overrides_ctx)
    return resolve_overrides(ovloader.fetch(ov), ov, base_url)


def recursive_resolve_and_validate_document(
    loadingContext: LoadingContext,
    workflowobj: Union[CommentedMap, CommentedSeq],
    uri: str,
    preprocess_only: bool = False,
    skip_schemas: Optional[bool] = None,
) -> Tuple[LoadingContext, str, Process]:
    """Validate a CWL document, checking that a tool object can be built."""
    loadingContext, uri = resolve_and_validate_document(
        loadingContext,
        workflowobj,
        uri,
        preprocess_only=preprocess_only,
        skip_schemas=skip_schemas,
    )
    tool = make_tool(uri, loadingContext)
    return loadingContext, uri, tool
