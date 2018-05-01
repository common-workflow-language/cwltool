import json
from collections import namedtuple
import logging

from typing import Any, Callable, Dict, Generator, Iterable, List, Text, Union, cast
import six

from schema_salad.sourceline import SourceLine, cmap, strip_dup_lineno, indent, bullets
import schema_salad.validate as validate
from .process import shortname
from .errors import WorkflowException

_logger = logging.getLogger("cwltool")

def _get_type(tp):
    # type: (Any) -> Any
    if isinstance(tp, dict):
        if tp.get("type") not in ("array", "record", "enum"):
            return tp["type"]
    return tp

def check_types(srctype, sinktype, linkMerge, valueFrom):
    # type: (Any, Any, Text, Text) -> Text
    """Check if the source and sink types are "pass", "warning", or "exception".
    """

    if valueFrom:
        return "pass"
    elif not linkMerge:
        if can_assign_src_to_sink(srctype, sinktype, strict=True):
            return "pass"
        elif can_assign_src_to_sink(srctype, sinktype, strict=False):
            return "warning"
        else:
            return "exception"
    elif linkMerge == "merge_nested":
        return check_types({"items": _get_type(srctype), "type": "array"}, _get_type(sinktype), None, None)
    elif linkMerge == "merge_flattened":
        return check_types(merge_flatten_type(_get_type(srctype)), _get_type(sinktype), None, None)
    else:
        raise WorkflowException(u"Unrecognized linkMerge enu_m '%s'" % linkMerge)


def merge_flatten_type(src):
    # type: (Any) -> Any
    """Return the merge flattened type of the source type
    """

    if isinstance(src, list):
        return [merge_flatten_type(t) for t in src]
    elif isinstance(src, dict) and src.get("type") == "array":
        return src
    else:
        return {"items": src, "type": "array"}


def can_assign_src_to_sink(src, sink, strict=False):  # type: (Any, Any, bool) -> bool
    """Check for identical type specifications, ignoring extra keys like inputBinding.

    src: admissible source types
    sink: admissible sink types

    In non-strict comparison, at least one source type must match one sink type.
    In strict comparison, all source types must match at least one sink type.
    """

    if src == "Any" or sink == "Any":
        return True
    if isinstance(src, dict) and isinstance(sink, dict):
        if src["type"] == "array" and sink["type"] == "array":
            return can_assign_src_to_sink(src["items"], sink["items"], strict)
        elif src["type"] == "record" and sink["type"] == "record":
            return _compare_records(src, sink, strict)
        elif src["type"] == "File" and sink["type"] == "File":
            for sinksf in sink.get("secondaryFiles", []):
                if not [1 for srcsf in src.get("secondaryFiles", []) if sinksf == srcsf]:
                    if strict:
                        return False
            return True
        else:
            return can_assign_src_to_sink(src["type"], sink["type"], strict)
    elif isinstance(src, list):
        if strict:
            for t in src:
                if not can_assign_src_to_sink(t, sink):
                    return False
            return True
        else:
            for t in src:
                if can_assign_src_to_sink(t, sink):
                    return True
            return False
    elif isinstance(sink, list):
        for t in sink:
            if can_assign_src_to_sink(src, t):
                return True
        return False
    else:
        return src == sink


def _compare_records(src, sink, strict=False):
    # type: (Dict[Text, Any], Dict[Text, Any], bool) -> bool
    """Compare two records, ensuring they have compatible fields.

    This handles normalizing record names, which will be relative to workflow
    step, so that they can be compared.
    """

    def _rec_fields(rec):  # type: (Dict[Text, Any]) -> Dict[Text, Any]
        out = {}
        for field in rec["fields"]:
            name = shortname(field["name"])
            out[name] = field["type"]
        return out

    srcfields = _rec_fields(src)
    sinkfields = _rec_fields(sink)
    for key in six.iterkeys(sinkfields):
        if (not can_assign_src_to_sink(
                srcfields.get(key, "null"), sinkfields.get(key, "null"), strict)
            and sinkfields.get(key) is not None):
            _logger.info("Record comparison failure for %s and %s\n"
                         "Did not match fields for %s: %s and %s" %
                         (src["name"], sink["name"], key, srcfields.get(key),
                          sinkfields.get(key)))
            return False
    return True

def static_checker(workflow_inputs, workflow_outputs, step_inputs, step_outputs):
    # type: (List[Dict[Text, Any]], List[Dict[Text, Any]], List[Dict[Text, Any]], List[Dict[Text, Any]]) -> None
    """Check if all source and sink types of a workflow are compatible before run time.
    """

    # source parameters: workflow_inputs and step_outputs
    # sink parameters: step_inputs and workflow_outputs

    # make a dictionary of source parameters, indexed by the "id" field
    src_parms = workflow_inputs + step_outputs
    src_dict = {}
    for parm in src_parms:
        src_dict[parm["id"]] = parm

    step_inputs_val = check_all_types(src_dict, step_inputs, "source")
    workflow_outputs_val = check_all_types(src_dict, workflow_outputs, "outputSource")

    warnings = step_inputs_val["warning"] + workflow_outputs_val["warning"]
    exceptions = step_inputs_val["exception"] + workflow_outputs_val["exception"]

    warning_msgs = []
    exception_msgs = []
    for warning in warnings:
        src = warning.src
        sink = warning.sink
        linkMerge = warning.linkMerge
        if sink.get("secondaryFiles") and sorted(sink.get("secondaryFiles",[])) != sorted(src.get("secondaryFiles",[])):
            msg1 = "Sink '%s'" % (shortname(sink["id"]))
            msg2 = SourceLine(sink.get("_tool_entry", sink), "secondaryFiles").makeError(
                "expects secondaryFiles: %s but" % (sink.get("secondaryFiles")))
            if "secondaryFiles" in src:
                msg3 = SourceLine(src, "secondaryFiles").makeError(
                    "source '%s' has secondaryFiles %s." % (shortname(src["id"]), src.get("secondaryFiles")))
            else:
                msg3 = SourceLine(src, "id").makeError(
                    "source '%s' does not include secondaryFiles." % (shortname(src["id"])))
            msg4 = SourceLine(src, "id").makeError("To fix, add secondaryFiles: %s to definition of '%s'." % (sink.get("secondaryFiles"), shortname(src["id"])))
            msg = SourceLine(sink).makeError("%s\n%s" % (msg1, bullets([msg2, msg3, msg4], "  ")))
        else:
            msg = SourceLine(src, "type").makeError(
                "Source '%s' of type %s may be incompatible"
                % (shortname(src["id"]), json.dumps(src["type"]))) + "\n" + \
                SourceLine(sink, "type").makeError(
                "  with sink '%s' of type %s"
                % (shortname(sink["id"]), json.dumps(sink["type"])))
            if linkMerge:
                msg += "\n" + SourceLine(sink).makeError("  source has linkMerge method %s" % linkMerge)

        warning_msgs.append(msg)
    for exception in exceptions:
        src = exception.src
        sink = exception.sink
        linkMerge = exception.linkMerge
        msg = SourceLine(src, "type").makeError(
            "Source '%s' of type %s is incompatible"
            % (shortname(src["id"]), json.dumps(src["type"]))) + "\n" + \
            SourceLine(sink, "type").makeError(
            "  with sink '%s' of type %s"
            % (shortname(sink["id"]), json.dumps(sink["type"])))
        if linkMerge:
            msg += "\n" + SourceLine(sink).makeError("  source has linkMerge method %s" % linkMerge)
        exception_msgs.append(msg)

    for sink in step_inputs:
        if ('null' != sink["type"] and 'null' not in sink["type"]
            and "source" not in sink and "default" not in sink and "valueFrom" not in sink):
            msg = SourceLine(sink).makeError(
                "Required parameter '%s' does not have source, default, or valueFrom expression"
                % shortname(sink["id"]))
            exception_msgs.append(msg)

    all_warning_msg = strip_dup_lineno("\n".join(warning_msgs))
    all_exception_msg = strip_dup_lineno("\n".join(exception_msgs))

    if warnings:
        _logger.warning("Workflow checker warning:\n%s" % all_warning_msg)
    if exceptions:
        raise validate.ValidationException(all_exception_msg)


SrcSink = namedtuple("SrcSink", ["src", "sink", "linkMerge"])

def check_all_types(src_dict, sinks, sourceField):
    # type: (Dict[Text, Any], List[Dict[Text, Any]], Text) -> Dict[Text, List[SrcSink]]
    # sourceField is either "soure" or "outputSource"
    """Given a list of sinks, check if their types match with the types of their sources.
    """

    validation = {"warning": [], "exception": []}  # type: Dict[Text, List[SrcSink]]
    for sink in sinks:
        if sourceField in sink:
            valueFrom = sink.get("valueFrom")
            if isinstance(sink[sourceField], list):
                srcs_of_sink = [src_dict[parm_id] for parm_id in sink[sourceField]]
                linkMerge = sink.get("linkMerge", ("merge_nested"
                                                   if len(sink[sourceField]) > 1 else None))
            else:
                parm_id = sink[sourceField]
                srcs_of_sink = [src_dict[parm_id]]
                linkMerge = None
            for src in srcs_of_sink:
                check_result = check_types(src, sink, linkMerge, valueFrom)
                if check_result == "warning":
                    validation["warning"].append(SrcSink(src, sink, linkMerge))
                elif check_result == "exception":
                    validation["exception"].append(SrcSink(src, sink, linkMerge))
    return validation
