"""Loads a CWL document."""
from __future__ import absolute_import

import hashlib
import logging
import os
import re
import uuid
from typing import (Any, Callable, Dict, List, MutableMapping, MutableSequence,
                    Optional, Tuple, Union, cast)

import requests.sessions
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad import schema
from schema_salad.ref_resolver import (ContextType,  # pylint: disable=unused-import
                                       Fetcher, Loader, file_uri, SubLoader)
from schema_salad.sourceline import SourceLine, cmap
from schema_salad.validate import ValidationException
from six import itervalues, string_types
from six.moves import urllib
from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from . import process, update
from .context import LoadingContext  # pylint: disable=unused-import
from .errors import WorkflowException
from .loghandler import _logger
from .process import (Process, get_schema,  # pylint: disable=unused-import
                      shortname)
from .software_requirements import (  # pylint: disable=unused-import
    DependenciesConfiguration)
from .update import ALLUPDATES
from .utils import json_dumps




jobloaderctx = {
    u"cwl": "https://w3id.org/cwl/cwl#",
    u"cwltool": "http://commonwl.org/cwltool#",
    u"path": {u"@type": u"@id"},
    u"location": {u"@type": u"@id"},
    u"format": {u"@type": u"@id"},
    u"id": u"@id"
}  # type: ContextType


overrides_ctx = {
    u"overrideTarget": {u"@type": u"@id"},
    u"cwltool": "http://commonwl.org/cwltool#",
    u"http://commonwl.org/cwltool#overrides": {
        "@id": "cwltool:overrides",
        "mapSubject": "overrideTarget",
    },
    "requirements": {
        "@id": "https://w3id.org/cwl/cwl#requirements",
        "mapSubject": "class"
    }
}  # type: ContextType


FetcherConstructorType = Callable[
    [Dict[Text, Union[Text, bool]], requests.sessions.Session], Fetcher]
ResolverType = Callable[[Loader, Union[Text, Dict[Text, Any]]], Text]

def default_loader(fetcher_constructor=None):
    # type: (Optional[FetcherConstructorType]) -> Loader
    return Loader(jobloaderctx, fetcher_constructor=fetcher_constructor)

def resolve_tool_uri(argsworkflow,  # type: Text
                     resolver=None,  # type: ResolverType
                     fetcher_constructor=None,  # type: FetcherConstructorType
                     document_loader=None  # type: Loader
                    ):  # type: (...) -> Tuple[Text, Text]

    uri = None  # type: Optional[Text]
    split = urllib.parse.urlsplit(argsworkflow)
    # In case of Windows path, urlsplit misjudge Drive letters as scheme, here we are skipping that
    if split.scheme and split.scheme in [u'http', u'https', u'file']:
        uri = argsworkflow
    elif os.path.exists(os.path.abspath(argsworkflow)):
        uri = file_uri(str(os.path.abspath(argsworkflow)))
    elif resolver is not None:
        if document_loader is None:
            document_loader = default_loader(fetcher_constructor)  # type: ignore
        uri = resolver(document_loader, argsworkflow)

    if uri is None:
        raise ValidationException("Not found: '%s'" % argsworkflow)

    if argsworkflow != uri:
        _logger.info("Resolved '%s' to '%s'", argsworkflow, uri)

    fileuri = urllib.parse.urldefrag(uri)[0]
    return uri, fileuri


def fetch_document(argsworkflow,        # type: Union[Text, Dict[Text, Any]]
                   loadingContext=None  # type: Optional[LoadingContext]
                  ):  # type: (...) -> Tuple[LoadingContext, CommentedMap, Text]
    """Retrieve a CWL document."""
    if loadingContext is None:
        loadingContext = LoadingContext()
        loadingContext.loader = default_loader()
    else:
        loadingContext = loadingContext.copy()
        if loadingContext.loader is None:
            loadingContext.loader = default_loader(loadingContext.fetcher_constructor)

    if isinstance(argsworkflow, string_types):
        uri, fileuri = resolve_tool_uri(argsworkflow,
                                        resolver=loadingContext.resolver,
                                        document_loader=loadingContext.loader)
        workflowobj = loadingContext.loader.fetch(fileuri)
        return loadingContext, workflowobj, uri
    if isinstance(argsworkflow, dict):
        uri = argsworkflow["id"] if argsworkflow.get("id") else "_:" + Text(uuid.uuid4())
        workflowobj = cast(CommentedMap, cmap(argsworkflow, fn=uri))
        loadingContext.loader.idx[uri] = workflowobj
        return loadingContext, workflowobj, uri
    raise ValidationException("Must be URI or object: '%s'" % argsworkflow)


def _convert_stdstreams_to_files(workflowobj):
    # type: (Union[Dict[Text, Any], List[Dict[Text, Any]]]) -> None

    if isinstance(workflowobj, MutableMapping):
        if workflowobj.get('class') == 'CommandLineTool':
            with SourceLine(workflowobj, "outputs", ValidationException,
                            _logger.isEnabledFor(logging.DEBUG)):
                outputs = workflowobj.get('outputs', [])
                if not isinstance(outputs, CommentedSeq):
                    raise ValidationException('"outputs" section is not '
                                              'valid.')
                for out in workflowobj.get('outputs', []):
                    if not isinstance(out, CommentedMap):
                        raise ValidationException(
                            "Output '{}' is not a valid "
                            "OutputParameter.".format(out))
                    for streamtype in ['stdout', 'stderr']:
                        if out.get('type') == streamtype:
                            if 'outputBinding' in out:
                                raise ValidationException(
                                    "Not allowed to specify outputBinding when"
                                    " using %s shortcut." % streamtype)
                            if streamtype in workflowobj:
                                filename = workflowobj[streamtype]
                            else:
                                filename = Text(
                                    hashlib.sha1(  # nosec
                                        json_dumps(workflowobj, sort_keys=True
                                                  ).encode('utf-8')).hexdigest())
                                workflowobj[streamtype] = filename
                            out['type'] = 'File'
                            out['outputBinding'] = cmap({'glob': filename})
            for inp in workflowobj.get('inputs', []):
                if inp.get('type') == 'stdin':
                    if 'inputBinding' in inp:
                        raise ValidationException(
                            "Not allowed to specify inputBinding when"
                            " using stdin shortcut.")
                    if 'stdin' in workflowobj:
                        raise ValidationException(
                            "Not allowed to specify stdin path when"
                            " using stdin type shortcut.")
                    else:
                        workflowobj['stdin'] = \
                            "$(inputs.%s.path)" % \
                            inp['id'].rpartition('#')[2]
                        inp['type'] = 'File'
        else:
            for entry in itervalues(workflowobj):
                _convert_stdstreams_to_files(entry)
    if isinstance(workflowobj, MutableSequence):
        for entry in workflowobj:
            _convert_stdstreams_to_files(entry)

def _add_blank_ids(workflowobj):
    # type: (Union[Dict[Text, Any], List[Dict[Text, Any]]]) -> None

    if isinstance(workflowobj, MutableMapping):
        if ("run" in workflowobj and
                isinstance(workflowobj["run"], MutableMapping) and
                "id" not in workflowobj["run"] and
                "$import" not in workflowobj["run"]):
            workflowobj["run"]["id"] = Text(uuid.uuid4())
        for entry in itervalues(workflowobj):
            _add_blank_ids(entry)
    if isinstance(workflowobj, MutableSequence):
        for entry in workflowobj:
            _add_blank_ids(entry)

def resolve_and_validate_document(loadingContext,
                      workflowobj,
                      uri,
                      preprocess_only=False,     # type: bool
                      skip_schemas=None,         # type: bool
                     ):
    # type: (...) -> Tuple[LoadingContext, Text]
    """Validate a CWL document."""
    loadingContext = loadingContext.copy()

    if not isinstance(workflowobj, MutableMapping):
        raise ValueError("workflowjobj must be a dict, got '{}': {}".format(
            type(workflowobj), workflowobj))

    jobobj = None
    if "cwl:tool" in workflowobj:
        jobobj, _ = loadingContext.loader.resolve_all(workflowobj, uri)
        uri = urllib.parse.urljoin(uri, workflowobj["https://w3id.org/cwl/cwl#tool"])
        del cast(dict, jobobj)["https://w3id.org/cwl/cwl#tool"]

        workflowobj = fetch_document(uri, loadingContext)[1]

    fileuri = urllib.parse.urldefrag(uri)[0]

    cwlVersion = loadingContext.metadata.get("cwlVersion")
    if not cwlVersion:
        cwlVersion = workflowobj.get("cwlVersion")
    if not cwlVersion and fileuri != uri:
        # The tool we're loading is a fragment of a bigger file.  Get
        # the document root element and look for cwlVersion there.
        metadata = fetch_document(fileuri, loadingContext)[1]
        cwlVersion = metadata.get("cwlVersion")
    if not cwlVersion:
        raise ValidationException(
            "No cwlVersion found. "
            "Use the following syntax in your CWL document to declare "
            "the version: cwlVersion: <version>.\n"
            "Note: if this is a CWL draft-2 (pre v1.0) document then it "
            "will need to be upgraded first.")

    if not isinstance(cwlVersion, string_types):
        with SourceLine(workflowobj, "cwlVersion", ValidationException):
            raise ValidationException("'cwlVersion' must be a string, "
                                      "got {}".format(
                                          type(cwlVersion)))
    # strip out version
    cwlVersion = re.sub(
        r"^(?:cwl:|https://w3id.org/cwl/cwl#)", "",
        cwlVersion)
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
            "\n{}".format("\n".join(versions)))

    if isinstance(jobobj, CommentedMap) and "http://commonwl.org/cwltool#overrides" in jobobj:
        loadingContext.overrides_list.extend(resolve_overrides(jobobj, uri, uri))
        del jobobj["http://commonwl.org/cwltool#overrides"]

    if isinstance(jobobj, CommentedMap) and "https://w3id.org/cwl/cwl#requirements" in jobobj:
        if cwlVersion not in ("v1.1.0-dev1","v1.1"):
            raise ValidationException(
                    "`cwl:requirements` in the input object is not part of CWL "
                    "v1.0. You can adjust to use `cwltool:overrides` instead; or you "
                    "can set the cwlVersion to v1.1 or greater.")
        loadingContext.overrides_list.append({"overrideTarget": uri,
                                              "requirements": jobobj["https://w3id.org/cwl/cwl#requirements"]})
        del jobobj["https://w3id.org/cwl/cwl#requirements"]

    (sch_document_loader, avsc_names) = \
        process.get_schema(cwlVersion)[:2]

    if isinstance(avsc_names, Exception):
        raise avsc_names

    processobj = None  # type: Union[CommentedMap, CommentedSeq, Text, None]
    document_loader = Loader(sch_document_loader.ctx,
                             schemagraph=sch_document_loader.graph,
                             idx=loadingContext.loader.idx,
                             cache=sch_document_loader.cache,
                             fetcher_constructor=loadingContext.fetcher_constructor,
                             skip_schemas=skip_schemas)

    if cwlVersion == "v1.0":
        _add_blank_ids(workflowobj)

    processobj, metadata = document_loader.resolve_all(workflowobj, fileuri)
    if loadingContext.metadata:
        metadata = loadingContext.metadata
    if not isinstance(processobj, (CommentedMap, CommentedSeq)):
        raise ValidationException("Workflow must be a CommentedMap or CommentedSeq.")
    if not isinstance(metadata, CommentedMap):
        raise ValidationException("metadata must be a CommentedMap, was %s" % type(metadata))

    _convert_stdstreams_to_files(workflowobj)

    if preprocess_only:
        return loadingContext, uri

    if loadingContext.do_validate:
        schema.validate_doc(avsc_names, processobj, document_loader, loadingContext.strict)

    # None means default behavior (do update)
    if loadingContext.do_update in (True, None):
        if "cwlVersion" not in metadata:
            metadata["cwlVersion"] = cwlVersion
        processobj = cast(CommentedMap, cmap(update.update(
            processobj, document_loader, fileuri, loadingContext.enable_dev, metadata)))
        if isinstance(processobj, MutableMapping):
            document_loader.idx[processobj["id"]] = processobj
        elif isinstance(processobj, MutableSequence):
            document_loader.idx[metadata["id"]] = metadata
            for po in processobj:
                document_loader.idx[po["id"]] = po
        else:
            raise Exception("'processobj' was not MutableMapping or MutableSequence %s" % type(processobj))

    if jobobj is not None:
        loadingContext.jobdefaults = jobobj

    loadingContext.loader = document_loader
    loadingContext.avsc_names = avsc_names
    loadingContext.metadata = metadata

    return loadingContext, uri


def make_tool(uri,                # type: Union[Text, CommentedMap, CommentedSeq]
              loadingContext      # type: LoadingContext
             ):  # type: (...) -> Process
    """Make a Python CWL object."""
    if loadingContext.loader is None:
        raise ValueError("loadingContext must have a loader")
    resolveduri, metadata = loadingContext.loader.resolve_ref(uri)

    processobj = None
    if isinstance(resolveduri, MutableSequence):
        for obj in resolveduri:
            if obj['id'].endswith('#main'):
                processobj = obj
                break
        if not processobj:
            raise WorkflowException(
                u"Tool file contains graph of multiple objects, must specify "
                "one of #%s" % ", #".join(
                    urllib.parse.urldefrag(i["id"])[1] for i in resolveduri
                    if "id" in i))
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


def load_tool(argsworkflow,         # type: Union[Text, Dict[Text, Any]]
              loadingContext=None   # type: Optional[LoadingContext]
             ):  # type: (...) -> Process

    loadingContext, workflowobj, uri = fetch_document(
        argsworkflow, loadingContext)

    loadingContext, uri = resolve_and_validate_document(
        loadingContext, workflowobj, uri)

    return make_tool(uri,
                     loadingContext)

def resolve_overrides(ov,      # Type: CommentedMap
                      ov_uri,  # Type: Text
                      baseurl  # type: Text
                     ):  # type: (...) -> List[Dict[Text, Any]]
    ovloader = Loader(overrides_ctx)
    ret, _ = ovloader.resolve_all(ov, baseurl)
    if not isinstance(ret, CommentedMap):
        raise Exception("Expected CommentedMap, got %s" % type(ret))
    cwl_docloader = get_schema("v1.0")[0]
    cwl_docloader.resolve_all(ret, ov_uri)
    return ret["http://commonwl.org/cwltool#overrides"]

def load_overrides(ov, base_url):  # type: (Text, Text) -> List[Dict[Text, Any]]
    ovloader = Loader(overrides_ctx)
    return resolve_overrides(ovloader.fetch(ov), ov, base_url)
