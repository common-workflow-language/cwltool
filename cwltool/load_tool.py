import os
import logging
import re
import urlparse
import sys
import json
from schema_salad.ref_resolver import Loader
import schema_salad.validate as validate
import schema_salad.schema as schema
from . import update
from . import process

_logger = logging.getLogger("cwltool")

def fetch_document(argsworkflow):
    document_loader = Loader({"cwl": "https://w3id.org/cwl/cwl#", "id": "@id"})

    jobobj = None
    uri = None  # type: str
    workflowobj = None  # type: Dict[unicode, Any]
    if isinstance(argsworkflow, basestring):
        split = urlparse.urlsplit(argsworkflow)
        if split.scheme:
            uri = argsworkflow
        else:
            uri = "file://" + os.path.abspath(argsworkflow)
        fileuri, urifrag = urlparse.urldefrag(uri)
        workflowobj = document_loader.fetch(fileuri)
    elif isinstance(argsworkflow, dict):
        workflowobj = argsworkflow
        uri = "#" + str(id(argsworkflow))
    else:
        raise validate.ValidationException("Must be URI or object: '%s'" % argsworkflow)

    return document_loader, workflowobj, uri


def validate_document(document_loader, workflowobj, uri, enable_dev=False, strict=True):
    jobobj = None
    if "cwl:tool" in workflowobj:
        jobobj = workflowobj
        uri = urlparse.urljoin(uri, jobobj["cwl:tool"])
        del jobobj["cwl:tool"]
        workflowobj = fetch_document(uri)

    if isinstance(workflowobj, list):
        workflowobj = {
            "$graph": workflowobj
        }

    fileuri, urifrag = urlparse.urldefrag(uri)

    if "cwlVersion" in workflowobj:
        workflowobj["cwlVersion"] = re.sub(r"^(?:cwl:|https://w3id.org/cwl/cwl#)", "", workflowobj["cwlVersion"])
    else:
        workflowobj["cwlVersion"] = "draft-2"

    if workflowobj["cwlVersion"] == "draft-2":
        workflowobj = update._draft2toDraft3dev1(workflowobj, document_loader, uri, updateSteps=False)
        if "@graph" in workflowobj:
            workflowobj["$graph"] = workflowobj["@graph"]
            del workflowobj["@graph"]

    (document_loader, avsc_names, schema_metadata, schema_loader) = process.get_schema(workflowobj["cwlVersion"])

    if isinstance(avsc_names, Exception):
        raise avsc_names

    workflowobj["id"] = fileuri
    processobj, metadata = schema.load_and_validate(document_loader, avsc_names, workflowobj, strict)

    if not metadata:
        metadata = {"$namespaces": processobj.get("$namespaces", {}),
                   "$schemas": processobj.get("$schemas", []),
                   "cwlVersion": processobj["cwlVersion"]}

    if metadata.get("cwlVersion") != update.latest:
        processobj = update.update(processobj, document_loader, fileuri, enable_dev, metadata)

    if jobobj:
        metadata["cwl:defaults"] = jobobj

    return document_loader, avsc_names, processobj, metadata, uri


def make_tool(document_loader, avsc_names, processobj, metadata, uri, makeTool, kwargs):
    processobj, _ = document_loader.resolve_ref(uri)

    if isinstance(processobj, list):
        if 1 == len(processobj):
            processobj = processobj[0]
        else:
            raise WorkflowException(u"Tool file contains graph of multiple objects, "
                                   "must specify one of #%s" %
                                   ", #".join(urlparse.urldefrag(i["id"])[1]
                                              for i in processobj if "id" in i))

    kwargs = kwargs.copy()
    kwargs.update({
        "makeTool": makeTool,
        "loader": document_loader,
        "avsc_names": avsc_names,
        "metadata": metadata
    })
    t = makeTool(processobj, **kwargs)

    if "cwl:defaults" in metadata:
        jobobj = metadata["cwl:defaults"]
        for inp in t.tool["inputs"]:
            if shortname(inp["id"]) in jobobj:
                inp["default"] = jobobj[shortname(inp["id"])]

    return t


def load_tool(argsworkflow, makeTool, kwargs=None,
              enable_dev=False,
              strict=True):

    document_loader, workflowobj, uri = fetch_document(argsworkflow)
    document_loader, avsc_names, processobj, metadata, uri = validate_document(document_loader,
                                                                               workflowobj,
                                                                               uri,
                                                                               enable_dev=enable_dev,
                                                                               strict=strict)
    return make_tool(document_loader, avsc_names, processobj, metadata, uri, makeTool, kwargs if kwargs else {})
