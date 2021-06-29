"""Static checking of CWL workflow connectivity."""
from collections import namedtuple
from typing import (
    Any,
    Dict,
    List,
    MutableMapping,
    MutableSequence,
    Optional,
    Sized,
    Union,
    cast,
)

from schema_salad.exceptions import ValidationException
from schema_salad.sourceline import SourceLine, bullets, strip_dup_lineno
from schema_salad.utils import json_dumps

from .errors import WorkflowException
from .loghandler import _logger
from .process import shortname
from .utils import CWLObjectType, CWLOutputAtomType, CWLOutputType, SinkType, aslist


def _get_type(tp):
    # type: (Any) -> Any
    if isinstance(tp, MutableMapping):
        if tp.get("type") not in ("array", "record", "enum"):
            return tp["type"]
    return tp


def check_types(
    srctype: SinkType,
    sinktype: SinkType,
    linkMerge: Optional[str],
    valueFrom: Optional[str],
) -> str:
    """
    Check if the source and sink types are correct.

    Acceptable types are "pass", "warning", or "exception".
    """
    if valueFrom is not None:
        return "pass"
    if linkMerge is None:
        if can_assign_src_to_sink(srctype, sinktype, strict=True):
            return "pass"
        if can_assign_src_to_sink(srctype, sinktype, strict=False):
            return "warning"
        return "exception"
    if linkMerge == "merge_nested":
        return check_types(
            {"items": _get_type(srctype), "type": "array"},
            _get_type(sinktype),
            None,
            None,
        )
    if linkMerge == "merge_flattened":
        return check_types(
            merge_flatten_type(_get_type(srctype)), _get_type(sinktype), None, None
        )
    raise WorkflowException(f"Unrecognized linkMerge enum '{linkMerge}'")


def merge_flatten_type(src: SinkType) -> CWLOutputType:
    """Return the merge flattened type of the source type."""
    if isinstance(src, MutableSequence):
        return [merge_flatten_type(cast(SinkType, t)) for t in src]
    if isinstance(src, MutableMapping) and src.get("type") == "array":
        return src
    return {"items": src, "type": "array"}


def can_assign_src_to_sink(
    src: SinkType, sink: Optional[SinkType], strict: bool = False
) -> bool:
    """
    Check for identical type specifications, ignoring extra keys like inputBinding.

    src: admissible source types
    sink: admissible sink types

    In non-strict comparison, at least one source type must match one sink type.
    In strict comparison, all source types must match at least one sink type.
    """
    if src == "Any" or sink == "Any":
        return True
    if isinstance(src, MutableMapping) and isinstance(sink, MutableMapping):
        if sink.get("not_connected") and strict:
            return False
        if src["type"] == "array" and sink["type"] == "array":
            return can_assign_src_to_sink(
                cast(MutableSequence[CWLOutputAtomType], src["items"]),
                cast(MutableSequence[CWLOutputAtomType], sink["items"]),
                strict,
            )
        if src["type"] == "record" and sink["type"] == "record":
            return _compare_records(src, sink, strict)
        if src["type"] == "File" and sink["type"] == "File":
            for sinksf in cast(List[CWLObjectType], sink.get("secondaryFiles", [])):
                if not [
                    1
                    for srcsf in cast(
                        List[CWLObjectType], src.get("secondaryFiles", [])
                    )
                    if sinksf == srcsf
                ]:
                    if strict:
                        return False
            return True
        return can_assign_src_to_sink(
            cast(SinkType, src["type"]), cast(Optional[SinkType], sink["type"]), strict
        )
    if isinstance(src, MutableSequence):
        if strict:
            for this_src in src:
                if not can_assign_src_to_sink(cast(SinkType, this_src), sink):
                    return False
            return True
        for this_src in src:
            if can_assign_src_to_sink(cast(SinkType, this_src), sink):
                return True
        return False
    if isinstance(sink, MutableSequence):
        for this_sink in sink:
            if can_assign_src_to_sink(src, cast(SinkType, this_sink)):
                return True
        return False
    return bool(src == sink)


def _compare_records(
    src: CWLObjectType, sink: CWLObjectType, strict: bool = False
) -> bool:
    """
    Compare two records, ensuring they have compatible fields.

    This handles normalizing record names, which will be relative to workflow
    step, so that they can be compared.
    """

    def _rec_fields(
        rec,
    ):  # type: (MutableMapping[str, Any]) -> MutableMapping[str, Any]
        out = {}
        for field in rec["fields"]:
            name = shortname(field["name"])
            out[name] = field["type"]
        return out

    srcfields = _rec_fields(src)
    sinkfields = _rec_fields(sink)
    for key in sinkfields.keys():
        if (
            not can_assign_src_to_sink(
                srcfields.get(key, "null"), sinkfields.get(key, "null"), strict
            )
            and sinkfields.get(key) is not None
        ):
            _logger.info(
                "Record comparison failure for %s and %s\n"
                "Did not match fields for %s: %s and %s",
                src["name"],
                sink["name"],
                key,
                srcfields.get(key),
                sinkfields.get(key),
            )
            return False
    return True


def missing_subset(fullset: List[Any], subset: List[Any]) -> List[Any]:
    missing = []
    for i in subset:
        if i not in fullset:
            missing.append(i)
    return missing


def static_checker(
    workflow_inputs: List[CWLObjectType],
    workflow_outputs: MutableSequence[CWLObjectType],
    step_inputs: MutableSequence[CWLObjectType],
    step_outputs: List[CWLObjectType],
    param_to_step: Dict[str, CWLObjectType],
) -> None:
    """Check if all source and sink types of a workflow are compatible before run time."""
    # source parameters: workflow_inputs and step_outputs
    # sink parameters: step_inputs and workflow_outputs

    # make a dictionary of source parameters, indexed by the "id" field
    src_parms = workflow_inputs + step_outputs
    src_dict = {}  # type: Dict[str, CWLObjectType]
    for parm in src_parms:
        src_dict[cast(str, parm["id"])] = parm

    step_inputs_val = check_all_types(src_dict, step_inputs, "source", param_to_step)
    workflow_outputs_val = check_all_types(
        src_dict, workflow_outputs, "outputSource", param_to_step
    )

    warnings = step_inputs_val["warning"] + workflow_outputs_val["warning"]
    exceptions = step_inputs_val["exception"] + workflow_outputs_val["exception"]

    warning_msgs = []
    exception_msgs = []
    for warning in warnings:
        src = warning.src
        sink = warning.sink
        linkMerge = warning.linkMerge
        sinksf = sorted(
            p["pattern"]
            for p in sink.get("secondaryFiles", [])
            if p.get("required", True)
        )
        srcsf = sorted(p["pattern"] for p in src.get("secondaryFiles", []))
        # Every secondaryFile required by the sink, should be declared
        # by the source
        missing = missing_subset(srcsf, sinksf)
        if missing:
            msg1 = "Parameter '{}' requires secondaryFiles {} but".format(
                shortname(sink["id"]),
                missing,
            )
            msg3 = SourceLine(src, "id").makeError(
                "source '%s' does not provide those secondaryFiles."
                % (shortname(src["id"]))
            )
            msg4 = SourceLine(src.get("_tool_entry", src), "secondaryFiles").makeError(
                "To resolve, add missing secondaryFiles patterns to definition of '%s' or"
                % (shortname(src["id"]))
            )
            msg5 = SourceLine(
                sink.get("_tool_entry", sink), "secondaryFiles"
            ).makeError(
                "mark missing secondaryFiles in definition of '%s' as optional."
                % shortname(sink["id"])
            )
            msg = SourceLine(sink).makeError(
                "{}\n{}".format(msg1, bullets([msg3, msg4, msg5], "  "))
            )
        elif sink.get("not_connected"):
            if not sink.get("used_by_step"):
                msg = SourceLine(sink, "type").makeError(
                    "'%s' is not an input parameter of %s, expected %s"
                    % (
                        shortname(sink["id"]),
                        param_to_step[sink["id"]]["run"],
                        ", ".join(
                            shortname(cast(str, s["id"]))
                            for s in cast(
                                List[Dict[str, Union[str, bool]]],
                                param_to_step[sink["id"]]["inputs"],
                            )
                            if not s.get("not_connected")
                        ),
                    )
                )
            else:
                msg = ""
        else:
            msg = (
                SourceLine(src, "type").makeError(
                    "Source '%s' of type %s may be incompatible"
                    % (shortname(src["id"]), json_dumps(src["type"]))
                )
                + "\n"
                + SourceLine(sink, "type").makeError(
                    "  with sink '%s' of type %s"
                    % (shortname(sink["id"]), json_dumps(sink["type"]))
                )
            )
            if linkMerge is not None:
                msg += "\n" + SourceLine(sink).makeError(
                    "  source has linkMerge method %s" % linkMerge
                )

        if warning.message is not None:
            msg += "\n" + SourceLine(sink).makeError("  " + warning.message)

        if msg:
            warning_msgs.append(msg)

    for exception in exceptions:
        src = exception.src
        sink = exception.sink
        linkMerge = exception.linkMerge
        extra_message = exception.message
        msg = (
            SourceLine(src, "type").makeError(
                "Source '%s' of type %s is incompatible"
                % (shortname(src["id"]), json_dumps(src["type"]))
            )
            + "\n"
            + SourceLine(sink, "type").makeError(
                "  with sink '%s' of type %s"
                % (shortname(sink["id"]), json_dumps(sink["type"]))
            )
        )
        if extra_message is not None:
            msg += "\n" + SourceLine(sink).makeError("  " + extra_message)

        if linkMerge is not None:
            msg += "\n" + SourceLine(sink).makeError(
                "  source has linkMerge method %s" % linkMerge
            )
        exception_msgs.append(msg)

    for sink in step_inputs:
        if (
            "null" != sink["type"]
            and "null" not in sink["type"]
            and "source" not in sink
            and "default" not in sink
            and "valueFrom" not in sink
        ):
            msg = SourceLine(sink).makeError(
                "Required parameter '%s' does not have source, default, or valueFrom expression"
                % shortname(sink["id"])
            )
            exception_msgs.append(msg)

    all_warning_msg = strip_dup_lineno("\n".join(warning_msgs))
    all_exception_msg = strip_dup_lineno("\n" + "\n".join(exception_msgs))

    if all_warning_msg:
        _logger.warning("Workflow checker warning:\n%s", all_warning_msg)
    if exceptions:
        raise ValidationException(all_exception_msg)


SrcSink = namedtuple("SrcSink", ["src", "sink", "linkMerge", "message"])


def check_all_types(
    src_dict: Dict[str, CWLObjectType],
    sinks: MutableSequence[CWLObjectType],
    sourceField: str,
    param_to_step: Dict[str, CWLObjectType],
) -> Dict[str, List[SrcSink]]:
    """
    Given a list of sinks, check if their types match with the types of their sources.

    sourceField is either "soure" or "outputSource"
    """
    validation = {"warning": [], "exception": []}  # type: Dict[str, List[SrcSink]]
    for sink in sinks:
        if sourceField in sink:

            valueFrom = cast(Optional[str], sink.get("valueFrom"))
            pickValue = cast(Optional[str], sink.get("pickValue"))

            extra_message = None
            if pickValue is not None:
                extra_message = "pickValue is: %s" % pickValue

            if isinstance(sink[sourceField], MutableSequence):
                linkMerge = cast(
                    Optional[str],
                    sink.get(
                        "linkMerge",
                        (
                            "merge_nested"
                            if len(cast(Sized, sink[sourceField])) > 1
                            else None
                        ),
                    ),
                )  # type: Optional[str]

                if pickValue in ["first_non_null", "the_only_non_null"]:
                    linkMerge = None

                srcs_of_sink = []  # type: List[CWLObjectType]
                for parm_id in cast(MutableSequence[str], sink[sourceField]):
                    srcs_of_sink += [src_dict[parm_id]]
                    if (
                        is_conditional_step(param_to_step, parm_id)
                        and pickValue is None
                    ):
                        validation["warning"].append(
                            SrcSink(
                                src_dict[parm_id],
                                sink,
                                linkMerge,
                                message="Source is from conditional step, but pickValue is not used",
                            )
                        )
            else:
                parm_id = cast(str, sink[sourceField])
                srcs_of_sink = [src_dict[parm_id]]
                linkMerge = None

                if pickValue is not None:
                    validation["warning"].append(
                        SrcSink(
                            src_dict[parm_id],
                            sink,
                            linkMerge,
                            message="pickValue is used but only a single input source is declared",
                        )
                    )

                if is_conditional_step(param_to_step, parm_id):
                    src_typ = aslist(srcs_of_sink[0]["type"])
                    snk_typ = sink["type"]

                    if "null" not in src_typ:
                        src_typ = ["null"] + cast(List[Any], src_typ)

                    if "null" not in cast(
                        Union[List[str], CWLObjectType], snk_typ
                    ):  # Given our type names this works even if not a list
                        validation["warning"].append(
                            SrcSink(
                                src_dict[parm_id],
                                sink,
                                linkMerge,
                                message="Source is from conditional step and may produce `null`",
                            )
                        )

                    srcs_of_sink[0]["type"] = src_typ

            for src in srcs_of_sink:
                check_result = check_types(src, sink, linkMerge, valueFrom)
                if check_result == "warning":
                    validation["warning"].append(
                        SrcSink(src, sink, linkMerge, message=extra_message)
                    )
                elif check_result == "exception":
                    validation["exception"].append(
                        SrcSink(src, sink, linkMerge, message=extra_message)
                    )

    return validation


def is_conditional_step(param_to_step: Dict[str, CWLObjectType], parm_id: str) -> bool:
    source_step = param_to_step.get(parm_id)
    if source_step is not None:
        if source_step.get("when") is not None:
            return True
    return False
