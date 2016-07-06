# pylint: disable=unused-import
"""Loads a CWL document."""

import os
import uuid
import logging
import re
import urlparse
from schema_salad.ref_resolver import Loader
import schema_salad.validate as validate
from schema_salad.validate import ValidationException
import schema_salad.schema as schema
from avro.schema import Names
from . import update
from . import process
from .process import Process, shortname
from .errors import WorkflowException
from typing import Any, Callable, cast, Dict, Tuple, Union

_logger = logging.getLogger("cwltool")

def fetch_document(argsworkflow):
    # type: (Union[str, unicode, dict[unicode, Any]]) -> Tuple[Loader, Dict[unicode, Any], unicode]
    """Retrieve a CWL document."""
    document_loader = Loader({"cwl": "https://w3id.org/cwl/cwl#", "id": "@id"})

    uri = None  # type: unicode
    workflowobj = None  # type: Dict[unicode, Any]
    if isinstance(argsworkflow, (str, unicode)):
        split = urlparse.urlsplit(argsworkflow)
        if split.scheme:
            uri = argsworkflow
        else:
            uri = "file://" + os.path.abspath(argsworkflow)
        fileuri = urlparse.urldefrag(uri)[0]
        workflowobj = document_loader.fetch(fileuri)
    elif isinstance(argsworkflow, dict):
        workflowobj = argsworkflow
        uri = "#" + str(id(argsworkflow))
    else:
        raise ValidationException("Must be URI or object: '%s'" % argsworkflow)

    return document_loader, workflowobj, uri

def _convert_stdstreams_to_files(workflowobj):
    # type: (Union[Dict[unicode, Any], List[Dict[unicode, Any]]]) -> None

    if isinstance(workflowobj, dict):
        if ('class' in workflowobj
                and workflowobj['class'] == 'CommandLineTool'
                and 'outputs' in workflowobj):
            for out in workflowobj['outputs']:
                for streamtype in ['stdout', 'stderr']:
                    if out['type'] == streamtype:
                        if 'outputBinding' in out:
                            raise ValidationException(
                                    "Not allowed to specify outputBinding when"
                                    " using %s shortcut." % streamtype)
                        if streamtype in workflowobj:
                            filename = workflowobj[streamtype]
                        else:
                            filename = unicode(uuid.uuid4())
                            workflowobj[streamtype] = filename
                        out['type'] = 'File'
                        out['outputBinding'] = {'glob': filename}
    else:
        for entry in workflowobj:
            _convert_stdstreams_to_files(entry)

def validate_document(document_loader, workflowobj, uri,
                      enable_dev=False, strict=True, preprocess_only=False):
    # type: (Loader, Dict[unicode, Any], unicode, bool, bool, bool) -> Tuple[Loader, Names, Union[Dict[unicode, Any], List[Dict[unicode, Any]]], Dict[unicode, Any], unicode]
    """Validate a CWL document."""
    jobobj = None
    if "cwl:tool" in workflowobj:
        jobobj = workflowobj
        uri = urlparse.urljoin(uri, jobobj["cwl:tool"])
        del jobobj["cwl:tool"]
        workflowobj = fetch_document(uri)[1]

    if isinstance(workflowobj, list):
        workflowobj = {
            "$graph": workflowobj
        }

    fileuri = urlparse.urldefrag(uri)[0]

    if "cwlVersion" in workflowobj:
        workflowobj["cwlVersion"] = re.sub(
            r"^(?:cwl:|https://w3id.org/cwl/cwl#)", "",
            workflowobj["cwlVersion"])
    else:
        _logger.warn("No cwlVersion found, treating this file as draft-2.")
        workflowobj["cwlVersion"] = "draft-2"

    if workflowobj["cwlVersion"] == "draft-2":
        workflowobj = update._draft2toDraft3dev1(
            workflowobj, document_loader, uri, update_steps=False)
        if "@graph" in workflowobj:
            workflowobj["$graph"] = workflowobj["@graph"]
            del workflowobj["@graph"]

    (document_loader, avsc_names) = \
            process.get_schema(workflowobj["cwlVersion"])[:2]

    if isinstance(avsc_names, Exception):
        raise avsc_names

    workflowobj["id"] = fileuri
    processobj, metadata = document_loader.resolve_all(workflowobj, fileuri)
    if not isinstance(processobj, (dict, list)):
        raise ValidationException("Workflow must be a dict or list.")

    if not metadata:
        if not isinstance(processobj, dict):
            raise ValidationException("Draft-2 workflows must be a dict.")
        metadata = {"$namespaces": processobj.get("$namespaces", {}),
                   "$schemas": processobj.get("$schemas", []),
                   "cwlVersion": processobj["cwlVersion"]}

    _convert_stdstreams_to_files(workflowobj)

    if preprocess_only:
        return document_loader, avsc_names, processobj, metadata, uri

    schema.validate_doc(avsc_names, processobj, document_loader, strict)

    if metadata.get("cwlVersion") != update.LATEST:
        processobj = update.update(
            processobj, document_loader, fileuri, enable_dev, metadata)

    if jobobj:
        metadata[u"cwl:defaults"] = jobobj

    return document_loader, avsc_names, processobj, metadata, uri


def make_tool(document_loader, avsc_names, metadata, uri, makeTool, kwargs):
    # type: (Loader, Names, Dict[unicode, Any], unicode, Callable[..., Process], Dict[str, Any]) -> Process
    """Make a Python CWL object."""
    resolveduri = document_loader.resolve_ref(uri)[0]

    if isinstance(resolveduri, list):
        if len(resolveduri) == 1:
            processobj = resolveduri[0]
        else:
            raise WorkflowException(
                u"Tool file contains graph of multiple objects, must specify "
                "one of #%s" % ", #".join(
                    urlparse.urldefrag(i["id"])[1] for i in resolveduri
                    if "id" in i))
    else:
        processobj = resolveduri

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


def load_tool(argsworkflow, makeTool, kwargs=None,
              enable_dev=False,
              strict=True):
    # type: (Union[str,unicode,dict[unicode,Any]], Callable[...,Process], Dict[str, Any], bool, bool) -> Any
    document_loader, workflowobj, uri = fetch_document(argsworkflow)
    document_loader, avsc_names, processobj, metadata, uri = validate_document(
        document_loader, workflowobj, uri, enable_dev=enable_dev,
        strict=strict)
    return make_tool(document_loader, avsc_names, metadata, uri,
                     makeTool, kwargs if kwargs else {})
