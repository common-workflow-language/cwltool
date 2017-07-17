from __future__ import absolute_import
# pylint: disable=unused-import
"""Loads a CWL document."""

import logging
import os
import re
import uuid
from typing import Any, Callable, Dict, List, Text, Tuple, Union, cast

import requests.sessions
from six import itervalues, string_types

import schema_salad.schema as schema
from avro.schema import Names
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.ref_resolver import Fetcher, Loader, file_uri
from schema_salad.sourceline import cmap
from schema_salad.validate import ValidationException
from six.moves import urllib

from . import process, update
from .errors import WorkflowException
from .process import Process, shortname

_logger = logging.getLogger("cwltool")

jobloaderctx = {
    u"cwl": "https://w3id.org/cwl/cwl#",
    u"path": {u"@type": u"@id"},
    u"location": {u"@type": u"@id"},
    u"format": {u"@type": u"@id"},
    u"id": u"@id"
}

def fetch_document(argsworkflow,  # type: Union[Text, Dict[Text, Any]]
                   resolver=None,  # type: Callable[[Loader, Union[Text, Dict[Text, Any]]], Text]
                   fetcher_constructor=None
                   # type: Callable[[Dict[Text, Text], requests.sessions.Session], Fetcher]
                   ):
    # type: (...) -> Tuple[Loader, CommentedMap, Text]
    """Retrieve a CWL document."""

    document_loader = Loader(jobloaderctx, fetcher_constructor=fetcher_constructor)  # type: ignore

    uri = None  # type: Text
    workflowobj = None  # type: CommentedMap
    if isinstance(argsworkflow, string_types):
        split = urllib.parse.urlsplit(argsworkflow)
        # In case of Windows path, urlsplit misjudge Drive letters as scheme, here we are skipping that
        if split.scheme and split.scheme in [u'http',u'https',u'file']:
            uri = argsworkflow
        elif os.path.exists(os.path.abspath(argsworkflow)):
            uri = file_uri(str(os.path.abspath(argsworkflow)))
        elif resolver:
            uri = resolver(document_loader, argsworkflow)

        if uri is None:
            raise ValidationException("Not found: '%s'" % argsworkflow)

        if argsworkflow != uri:
            _logger.info("Resolved '%s' to '%s'", argsworkflow, uri)

        fileuri = urllib.parse.urldefrag(uri)[0]
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
                for streamtype in ['stdout', 'stderr']:
                    if out.get('type') == streamtype:
                        if 'outputBinding' in out:
                            raise ValidationException(
                                "Not allowed to specify outputBinding when"
                                " using %s shortcut." % streamtype)
                        if streamtype in workflowobj:
                            filename = workflowobj[streamtype]
                        else:
                            filename = Text(uuid.uuid4())
                            workflowobj[streamtype] = filename
                        out['type'] = 'File'
                        out['outputBinding'] = {'glob': filename}
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
                      fetcher_constructor=None,
                      skip_schemas=None
                      # type: Callable[[Dict[Text, Text], requests.sessions.Session], Fetcher]
                      ):
    # type: (...) -> Tuple[Loader, Names, Union[Dict[Text, Any], List[Dict[Text, Any]]], Dict[Text, Any], Text]
    """Validate a CWL document."""

    if isinstance(workflowobj, list):
        workflowobj = {
            "$graph": workflowobj
        }

    if not isinstance(workflowobj, dict):
        raise ValueError("workflowjobj must be a dict, got '%s': %s" % (type(workflowobj), workflowobj))

    jobobj = None
    if "cwl:tool" in workflowobj:
        jobobj, _ = document_loader.resolve_all(workflowobj, uri)
        uri = urllib.parse.urljoin(uri, workflowobj["https://w3id.org/cwl/cwl#tool"])
        del cast(dict, jobobj)["https://w3id.org/cwl/cwl#tool"]
        workflowobj = fetch_document(uri, fetcher_constructor=fetcher_constructor)[1]

    fileuri = urllib.parse.urldefrag(uri)[0]

    if "cwlVersion" in workflowobj:
        if not isinstance(workflowobj["cwlVersion"], (str, Text)):
            raise Exception("'cwlVersion' must be a string, got %s" % type(workflowobj["cwlVersion"]))
        workflowobj["cwlVersion"] = re.sub(
            r"^(?:cwl:|https://w3id.org/cwl/cwl#)", "",
            workflowobj["cwlVersion"])
    else:
        _logger.warning("No cwlVersion found, treating this file as draft-2.")
        workflowobj["cwlVersion"] = "draft-2"

    if workflowobj["cwlVersion"] == "draft-2":
        workflowobj = cast(CommentedMap, cmap(update._draft2toDraft3dev1(
            workflowobj, document_loader, uri, update_steps=False)))
        if "@graph" in workflowobj:
            workflowobj["$graph"] = workflowobj["@graph"]
            del workflowobj["@graph"]

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
    processobj, metadata = document_loader.resolve_all(workflowobj, fileuri)
    if not isinstance(processobj, (CommentedMap, CommentedSeq)):
        raise ValidationException("Workflow must be a dict or list.")

    if not metadata:
        if not isinstance(processobj, dict):
            raise ValidationException("Draft-2 workflows must be a dict.")
        metadata = cast(CommentedMap, cmap({"$namespaces": processobj.get("$namespaces", {}),
                                            "$schemas": processobj.get("$schemas", []),
                                            "cwlVersion": processobj["cwlVersion"]},
                                           fn=fileuri))

    _convert_stdstreams_to_files(workflowobj)

    if preprocess_only:
        return document_loader, avsc_names, processobj, metadata, uri

    schema.validate_doc(avsc_names, processobj, document_loader, strict)

    if metadata.get("cwlVersion") != update.LATEST:
        processobj = cast(CommentedMap, cmap(update.update(
            processobj, document_loader, fileuri, enable_dev, metadata)))

    if jobobj:
        metadata[u"cwl:defaults"] = jobobj

    return document_loader, avsc_names, processobj, metadata, uri


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

    if isinstance(resolveduri, list):
        if len(resolveduri) == 1:
            processobj = resolveduri[0]
        else:
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
              fetcher_constructor=None  # type: Callable[[Dict[Text, Text], requests.sessions.Session], Fetcher]
              ):
    # type: (...) -> Process

    document_loader, workflowobj, uri = fetch_document(argsworkflow, resolver=resolver,
                                                       fetcher_constructor=fetcher_constructor)
    document_loader, avsc_names, processobj, metadata, uri = validate_document(
        document_loader, workflowobj, uri, enable_dev=enable_dev,
        strict=strict, fetcher_constructor=fetcher_constructor)
    return make_tool(document_loader, avsc_names, metadata, uri,
                     makeTool, kwargs if kwargs else {})
