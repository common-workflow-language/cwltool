import os
from schema_salad.ref_resolver import Loader
import schema_salad.validate as validate
import urlparse
import sys
import update
import process

def load_tool(argsworkflow, updateonly, strict, makeTool, debug,
              print_pre=False,
              print_rdf=False,
              print_dot=False,
              print_deps=False,
              relative_deps=False,
              rdf_serializer=None,
              enable_dev=False,
              stdout=sys.stdout,
              urifrag=None):
    # type: (Union[str,unicode,dict[unicode,Any]], bool, bool, Callable[...,Process], bool, bool, bool, bool, bool, bool, Any, Any, Any) -> Any

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
        uri = urifrag
        fileuri = "#"
    else:
        raise validate.ValidationException("Must be URI or dict")

    if "cwl:tool" in workflowobj:
        jobobj = workflowobj
        uri = urlparse.urljoin(uri, jobobj["cwl:tool"])
        fileuri, urifrag = urlparse.urldefrag(uri)
        workflowobj = document_loader.fetch(fileuri)
        del jobobj["cwl:tool"]

    if isinstance(workflowobj, list):
        if enable_dev:
            # bare list without a version must be treated as draft-2
            workflowobj = {"cwlVersion": "https://w3id.org/cwl/cwl#draft-2",
                           "id": fileuri,
                           "@graph": workflowobj}
        else:
            raise validate.ValidationException("Missing 'cwlVersion'")

    workflowobj = update.update(workflowobj, document_loader, fileuri, enable_dev)
    document_loader.idx.clear()

    (document_loader, avsc_names, schema_metadata) = process.get_schema(workflowobj["cwlVersion"])

    if isinstance(avsc_names, Exception):
        raise avsc_names

    if updateonly:
        stdout.write(json.dumps(workflowobj, indent=4))
        return 0

    if print_deps:
        printdeps(workflowobj, document_loader, stdout, relative_deps)
        return 0

    try:
        processobj, metadata = schema_salad.schema.load_and_validate(document_loader, avsc_names, workflowobj, strict)
    except (validate.ValidationException, RuntimeError) as e:
        _logger.error(u"Tool definition failed validation:\n%s", e, exc_info=(e if debug else False))
        return 1

    if print_pre:
        stdout.write(json.dumps(processobj, indent=4))
        return 0

    if print_rdf:
        printrdf(argsworkflow, processobj, document_loader.ctx, rdf_serializer, stdout)
        return 0

    if print_dot:
        printdot(argsworkflow, processobj, document_loader.ctx, stdout)
        return 0

    if urifrag:
        processobj, _ = document_loader.resolve_ref(uri)
    elif isinstance(processobj, list):
        if 1 == len(processobj):
            processobj = processobj[0]
        else:
            _logger.error(u"Tool file contains graph of multiple objects, must specify one of #%s",
                          ", #".join(urlparse.urldefrag(i["id"])[1]
                                     for i in processobj if "id" in i))
            return 1

    if not metadata:
        metadata = {"$namespaces": processobj.get("$namespaces", {}), "$schemas": processobj.get("$schemas", []), 'cwlVersion': processobj["cwlVersion"]}

    try:
        t = makeTool(processobj, strict=strict, makeTool=makeTool, loader=document_loader, avsc_names=avsc_names, metadata=metadata)
    except (validate.ValidationException) as e:
        _logger.error(u"Tool definition failed validation:\n%s", e, exc_info=(e if debug else False))
        return 1
    except (RuntimeError, workflow.WorkflowException) as e:
        _logger.error(u"Tool definition failed initialization:\n%s", e, exc_info=(e if debug else False))
        return 1

    if jobobj:
        for inp in t.tool["inputs"]:
            if shortname(inp["id"]) in jobobj:
                inp["default"] = jobobj[shortname(inp["id"])]

    return t
