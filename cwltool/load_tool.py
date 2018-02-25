"""Loads a CWL document."""
from __future__ import absolute_import
# pylint: disable=unused-import

import logging
import os
import re
import uuid
import hashlib
import json
import copy
from typing import (Any, Callable, Dict, Iterable, List, Mapping, Optional,
        Text, Tuple, Union, cast)

import requests.sessions
from six import itervalues, string_types
from six.moves import urllib

import schema_salad.schema as schema
from avro.schema import Names
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.ref_resolver import ContextType, Fetcher, Loader, file_uri
from schema_salad.sourceline import cmap, SourceLine
from schema_salad.validate import ValidationException

from . import process, update
from .errors import WorkflowException
from .process import Process, shortname, get_schema
from .update import ALLUPDATES

_logger = logging.getLogger("cwltool")
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
    u"overrides": {
        "@id": "cwltool:overrides",
        "mapSubject": "overrideTarget",
    },
    "requirements": {
        "@id": "https://w3id.org/cwl/cwl#requirements",
        "mapSubject": "class"
    }
}  # type: ContextType


FetcherConstructorType = Callable[[Dict[Text, Union[Text, bool]],
    requests.sessions.Session], Fetcher]

loaders = {}  # type: Dict[FetcherConstructorType, Loader]

def default_loader(fetcher_constructor):
    # type: (Optional[FetcherConstructorType]) -> Loader
    if fetcher_constructor in loaders:
        return loaders[fetcher_constructor]
    else:
        loader = Loader(jobloaderctx, fetcher_constructor=fetcher_constructor)
        loaders[fetcher_constructor] = loader
        return loader

def resolve_tool_uri(argsworkflow,  # type: Text
                     resolver=None,  # type: Callable[[Loader, Union[Text, Dict[Text, Any]]], Text]
                     fetcher_constructor=None,  # type: FetcherConstructorType
                     document_loader=None  # type: Loader
                     ):  # type: (...) -> Tuple[Text, Text]

    uri = None  # type: Text
    split = urllib.parse.urlsplit(argsworkflow)
    # In case of Windows path, urlsplit misjudge Drive letters as scheme, here we are skipping that
    if split.scheme and split.scheme in [u'http', u'https', u'file']:
        uri = argsworkflow
    elif os.path.exists(os.path.abspath(argsworkflow)):
        uri = file_uri(str(os.path.abspath(argsworkflow)))
    elif resolver:
        if document_loader is None:
            document_loader = default_loader(fetcher_constructor)  # type: ignore
        uri = resolver(document_loader, argsworkflow)

    if uri is None:
        raise ValidationException("Not found: '%s'" % argsworkflow)

    if argsworkflow != uri:
        _logger.info("Resolved '%s' to '%s'", argsworkflow, uri)

    fileuri = urllib.parse.urldefrag(uri)[0]
    return uri, fileuri


def fetch_document(argsworkflow,  # type: Union[Text, Dict[Text, Any]]
                   resolver=None,  # type: Callable[[Loader, Union[Text, Dict[Text, Any]]], Text]
                   fetcher_constructor=None  # type: FetcherConstructorType
                  ):  # type: (...) -> Tuple[Loader, CommentedMap, Text]
    """Retrieve a CWL document."""

    document_loader = default_loader(fetcher_constructor)  # type: ignore

    uri = None  # type: Text
    workflowobj = None  # type: CommentedMap
    if isinstance(argsworkflow, string_types):
        uri, fileuri = resolve_tool_uri(argsworkflow, resolver=resolver,
                document_loader=document_loader)
        workflowobj = document_loader.fetch(fileuri)
    elif isinstance(argsworkflow, dict):
        uri = "#" + Text(id(argsworkflow))
        workflowobj = cast(CommentedMap, cmap(argsworkflow, fn=uri))
    else:
        raise ValidationException("Must be URI or object: '%s'" % argsworkflow)

    return document_loader, workflowobj, uri


def _convert_stdstreams_to_files(workflowobj):
    # type: (Union[Dict[Text, Any], List[Dict[Text, Any]]]) -> None

    if isinstance(workflowobj, dict):
        if workflowobj.get('class') == 'CommandLineTool':
            for out in workflowobj.get('outputs', []):
                if type(out) is not CommentedMap:
                    with SourceLine(workflowobj, "outputs", ValidationException, _logger.isEnabledFor(logging.DEBUG)):
                        raise ValidationException("Output '%s' is not a valid OutputParameter." % out)
                for streamtype in ['stdout', 'stderr']:
                    if out.get('type') == streamtype:
                        if 'outputBinding' in out:
                            raise ValidationException(
                                "Not allowed to specify outputBinding when"
                                " using %s shortcut." % streamtype)
                        if streamtype in workflowobj:
                            filename = workflowobj[streamtype]
                        else:
                            filename = Text(hashlib.sha1(json.dumps(workflowobj,
                                        sort_keys=True).encode('utf-8')).hexdigest())
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
    if isinstance(workflowobj, list):
        for entry in workflowobj:
            _convert_stdstreams_to_files(entry)

def _add_blank_ids(workflowobj):
    # type: (Union[Dict[Text, Any], List[Dict[Text, Any]]]) -> None

    if isinstance(workflowobj, dict):
        if ("run" in workflowobj and
            isinstance(workflowobj["run"], dict) and
            "id" not in workflowobj["run"] and
            "$import" not in workflowobj["run"]):
            workflowobj["run"]["id"] = Text(uuid.uuid4())
        for entry in itervalues(workflowobj):
            _add_blank_ids(entry)
    if isinstance(workflowobj, list):
        for entry in workflowobj:
            _add_blank_ids(entry)

def validate_document(document_loader,  # type: Loader
                      workflowobj,  # type: CommentedMap
                      uri,  # type: Text
                      enable_dev=False,  # type: bool
                      strict=True,  # type: bool
                      preprocess_only=False,  # type: bool
                      fetcher_constructor=None,  # type: FetcherConstructorType
                      skip_schemas=None,  # type: bool
                      overrides=None,  # type: List[Dict]
                      metadata=None,  # type: Optional[Dict]
                      ):
    # type: (...) -> Tuple[Loader, Names, Union[Dict[Text, Any], List[Dict[Text, Any]]], Dict[Text, Any], Text]
    """Validate a CWL document."""

    if isinstance(workflowobj, list):
        workflowobj = cmap({
            "$graph": workflowobj
        }, fn=uri)

    if not isinstance(workflowobj, dict):
        raise ValueError("workflowjobj must be a dict, got '%s': %s" % (type(workflowobj), workflowobj))

    jobobj = None
    if "cwl:tool" in workflowobj:
        job_loader = default_loader(fetcher_constructor)  # type: ignore
        jobobj, _ = job_loader.resolve_all(workflowobj, uri)
        uri = urllib.parse.urljoin(uri, workflowobj["https://w3id.org/cwl/cwl#tool"])
        del cast(dict, jobobj)["https://w3id.org/cwl/cwl#tool"]

        if "http://commonwl.org/cwltool#overrides" in jobobj:
            overrides.extend(resolve_overrides(jobobj, uri, uri))
            del jobobj["http://commonwl.org/cwltool#overrides"]

        workflowobj = fetch_document(uri, fetcher_constructor=fetcher_constructor)[1]

    fileuri = urllib.parse.urldefrag(uri)[0]
    if "cwlVersion" not in workflowobj:
        if metadata and 'cwlVersion' in metadata:
            workflowobj['cwlVersion'] = metadata['cwlVersion']
        else:
            raise ValidationException(
                  "No cwlVersion found. "
                  "Use the following syntax in your CWL document to declare the version: cwlVersion: <version>.\n"
                  "Note: if this is a CWL draft-2 (pre v1.0) document then it will need to be upgraded first.")

    if not isinstance(workflowobj["cwlVersion"], (str, Text)):
        raise Exception("'cwlVersion' must be a string, got %s" % type(workflowobj["cwlVersion"]))
    # strip out version
    workflowobj["cwlVersion"] = re.sub(
        r"^(?:cwl:|https://w3id.org/cwl/cwl#)", "",
        workflowobj["cwlVersion"])
    if workflowobj["cwlVersion"] not in list(ALLUPDATES):
        # print out all the Supported Versions of cwlVersion
        versions = []
        for version in list(ALLUPDATES):
            if "dev" in version:
                version += " (with --enable-dev flag only)"
            versions.append(version)
        versions.sort()
        raise ValidationException("The CWL reference runner no longer supports pre CWL v1.0 documents. "
                                  "Supported versions are: \n{}".format("\n".join(versions)))

    (sch_document_loader, avsc_names) = \
        process.get_schema(workflowobj["cwlVersion"])[:2]

    if isinstance(avsc_names, Exception):
        raise avsc_names

    processobj = None  # type: Union[CommentedMap, CommentedSeq, Text]
    document_loader = Loader(sch_document_loader.ctx, schemagraph=sch_document_loader.graph,
                             idx=document_loader.idx, cache=sch_document_loader.cache,
                             fetcher_constructor=fetcher_constructor, skip_schemas=skip_schemas)

    _add_blank_ids(workflowobj)

    workflowobj["id"] = fileuri
    processobj, new_metadata = document_loader.resolve_all(workflowobj, fileuri)
    if not isinstance(processobj, (CommentedMap, CommentedSeq)):
        raise ValidationException("Workflow must be a dict or list.")

    if not new_metadata:
        new_metadata = cast(CommentedMap, cmap(
            {"$namespaces": processobj.get("$namespaces", {}),
             "$schemas": processobj.get("$schemas", []),
             "cwlVersion": processobj["cwlVersion"]}, fn=fileuri))

    _convert_stdstreams_to_files(workflowobj)

    if preprocess_only:
        return document_loader, avsc_names, processobj, new_metadata, uri

    schema.validate_doc(avsc_names, processobj, document_loader, strict)

    if new_metadata.get("cwlVersion") != update.LATEST:
        processobj = cast(CommentedMap, cmap(update.update(
            processobj, document_loader, fileuri, enable_dev, new_metadata)))

    if jobobj:
        new_metadata[u"cwl:defaults"] = jobobj

    if overrides:
        new_metadata[u"cwltool:overrides"] = overrides

    return document_loader, avsc_names, processobj, new_metadata, uri


def make_tool(document_loader,  # type: Loader
              avsc_names,  # type: Names
              metadata,  # type: Dict[Text, Any]
              uri,  # type: Text
              makeTool,  # type: Callable[..., Process]
              kwargs  # type: dict
              ):
    # type: (...) -> Process
    """Make a Python CWL object."""
    resolveduri = document_loader.resolve_ref(uri)[0]

    processobj = None
    if isinstance(resolveduri, list):
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
    elif isinstance(resolveduri, dict):
        processobj = resolveduri
    else:
        raise Exception("Must resolve to list or dict")

    kwargs = kwargs.copy()
    kwargs.update({
        "makeTool": makeTool,
        "loader": document_loader,
        "avsc_names": avsc_names,
        "metadata": metadata
    })
    tool = makeTool(processobj, **kwargs)

    if "cwl:defaults" in metadata:
        jobobj = metadata["cwl:defaults"]
        for inp in tool.tool["inputs"]:
            if shortname(inp["id"]) in jobobj:
                inp["default"] = jobobj[shortname(inp["id"])]

    return tool


def load_tool(argsworkflow,  # type: Union[Text, Dict[Text, Any]]
              makeTool,  # type: Callable[..., Process]
              kwargs=None,  # type: Dict
              enable_dev=False,  # type: bool
              strict=True,  # type: bool
              resolver=None,  # type: Callable[[Loader, Union[Text, Dict[Text, Any]]], Text]
              fetcher_constructor=None,  # type: FetcherConstructorType
              overrides=None
              ):
    # type: (...) -> Process

    document_loader, workflowobj, uri = fetch_document(argsworkflow, resolver=resolver,
                                                       fetcher_constructor=fetcher_constructor)
    document_loader, avsc_names, processobj, metadata, uri = validate_document(
        document_loader, workflowobj, uri, enable_dev=enable_dev,
        strict=strict, fetcher_constructor=fetcher_constructor,
        overrides=overrides, metadata=kwargs.get('metadata', None)
        if kwargs else None)
    return make_tool(document_loader, avsc_names, metadata, uri,
                     makeTool, kwargs if kwargs else {})

def resolve_overrides(ov, ov_uri, baseurl):  # type: (CommentedMap, Text, Text) -> List[Dict[Text, Any]]
    ovloader = Loader(overrides_ctx)
    ret, _ = ovloader.resolve_all(ov, baseurl)
    if not isinstance(ret, CommentedMap):
        raise Exception("Expected CommentedMap, got %s" % type(ret))
    cwl_docloader = get_schema("v1.0")[0]
    cwl_docloader.resolve_all(ret, ov_uri)
    return ret["overrides"]

def load_overrides(ov, base_url):  # type: (Text, Text) -> List[Dict[Text, Any]]
    ovloader = Loader(overrides_ctx)
    return resolve_overrides(ovloader.fetch(ov), ov, base_url)
