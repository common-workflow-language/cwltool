"""Parse CWL expressions."""

import copy
import re
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Union,
)

from schema_salad.utils import json_dumps

from .errors import WorkflowException
from .sandboxjs import JavascriptException, default_timeout, execjs
from .utils import bytes2str_in_dicts, docker_windows_path_adjust


def jshead(engine_config, rootvars):
    # type: (List[str], Dict[str, Any]) -> str

    # make sure all the byte strings are converted
    # to str in `rootvars` dict.

    return "\n".join(
        engine_config
        + [
            "var {} = {};".format(k, json_dumps(v, indent=4))
            for k, v in rootvars.items()
        ]
    )


# decode all raw strings to unicode
seg_symbol = r"""\w+"""
seg_single = r"""\['([^']|\\')+'\]"""
seg_double = r"""\["([^"]|\\")+"\]"""
seg_index = r"""\[[0-9]+\]"""
segments = r"(\.%s|%s|%s|%s)" % (seg_symbol, seg_single, seg_double, seg_index)
segment_re = re.compile(segments, flags=re.UNICODE)
param_str = r"\((%s)%s*\)$" % (seg_symbol, segments)
param_re = re.compile(param_str, flags=re.UNICODE)

JSON = Union[Dict[Any, Any], List[Any], str, int, float, bool, None]


class SubstitutionError(Exception):
    pass


def scanner(scan):  # type: (str) -> List[int]
    DEFAULT = 0
    DOLLAR = 1
    PAREN = 2
    BRACE = 3
    SINGLE_QUOTE = 4
    DOUBLE_QUOTE = 5
    BACKSLASH = 6

    i = 0
    stack = [DEFAULT]
    start = 0
    while i < len(scan):
        state = stack[-1]
        c = scan[i]

        if state == DEFAULT:
            if c == "$":
                stack.append(DOLLAR)
            elif c == "\\":
                stack.append(BACKSLASH)
        elif state == BACKSLASH:
            stack.pop()
            if stack[-1] == DEFAULT:
                return [i - 1, i + 1]
        elif state == DOLLAR:
            if c == "(":
                start = i - 1
                stack.append(PAREN)
            elif c == "{":
                start = i - 1
                stack.append(BRACE)
            else:
                stack.pop()
        elif state == PAREN:
            if c == "(":
                stack.append(PAREN)
            elif c == ")":
                stack.pop()
                if stack[-1] == DOLLAR:
                    return [start, i + 1]
            elif c == "'":
                stack.append(SINGLE_QUOTE)
            elif c == '"':
                stack.append(DOUBLE_QUOTE)
        elif state == BRACE:
            if c == "{":
                stack.append(BRACE)
            elif c == "}":
                stack.pop()
                if stack[-1] == DOLLAR:
                    return [start, i + 1]
            elif c == "'":
                stack.append(SINGLE_QUOTE)
            elif c == '"':
                stack.append(DOUBLE_QUOTE)
        elif state == SINGLE_QUOTE:
            if c == "'":
                stack.pop()
            elif c == "\\":
                stack.append(BACKSLASH)
        elif state == DOUBLE_QUOTE:
            if c == '"':
                stack.pop()
            elif c == "\\":
                stack.append(BACKSLASH)
        i += 1

    if len(stack) > 1:
        raise SubstitutionError(
            "Substitution error, unfinished block starting at position {}: {}".format(
                start, scan[start:]
            )
        )
    else:
        return []


def next_seg(
    parsed_string, remaining_string, current_value
):  # type: (str, str, JSON) -> JSON
    if remaining_string:
        m = segment_re.match(remaining_string)
        if not m:
            return current_value
        next_segment_str = m.group(0)

        key = None  # type: Optional[Union[str, int]]
        if next_segment_str[0] == ".":
            key = next_segment_str[1:]
        elif next_segment_str[1] in ("'", '"'):
            key = next_segment_str[2:-2].replace("\\'", "'").replace('\\"', '"')

        if key is not None:
            if (
                isinstance(current_value, MutableSequence)
                and key == "length"
                and not remaining_string[m.end(0) :]
            ):
                return len(current_value)
            if not isinstance(current_value, MutableMapping):
                raise WorkflowException(
                    "%s is a %s, cannot index on string '%s'"
                    % (parsed_string, type(current_value).__name__, key)
                )
            if key not in current_value:
                raise WorkflowException(
                    "%s does not contain key '%s'" % (parsed_string, key)
                )
        else:
            try:
                key = int(next_segment_str[1:-1])
            except ValueError as v:
                raise WorkflowException(str(v)) from v
            if not isinstance(current_value, MutableSequence):
                raise WorkflowException(
                    "%s is a %s, cannot index on int '%s'"
                    % (parsed_string, type(current_value).__name__, key)
                )
            if key and key >= len(current_value):
                raise WorkflowException(
                    "%s list index %i out of range" % (parsed_string, key)
                )

        if isinstance(current_value, Mapping):
            try:
                return next_seg(
                    parsed_string + remaining_string,
                    remaining_string[m.end(0) :],
                    current_value[key],
                )
            except KeyError:
                raise WorkflowException(
                    "%s doesn't have property %s" % (parsed_string, key)
                )
        elif isinstance(current_value, list) and isinstance(key, int):
            try:
                return next_seg(
                    parsed_string + remaining_string,
                    remaining_string[m.end(0) :],
                    current_value[key],
                )
            except KeyError:
                raise WorkflowException(
                    "%s doesn't have property %s" % (parsed_string, key)
                )
        else:
            raise WorkflowException(
                "%s doesn't have property %s" % (parsed_string, key)
            )
    else:
        return current_value


def evaluator(
    ex,  # type: str
    jslib,  # type: str
    obj,  # type: Dict[str, Any]
    timeout,  # type: float
    fullJS=False,  # type: bool
    force_docker_pull=False,  # type: bool
    debug=False,  # type: bool
    js_console=False,  # type: bool
):
    # type: (...) -> JSON
    match = param_re.match(ex)

    expression_parse_exception = None
    expression_parse_succeeded = False

    if match is not None:
        first_symbol = match.group(1)
        first_symbol_end = match.end(1)

        if first_symbol_end + 1 == len(ex) and first_symbol == "null":
            return None
        try:
            if obj.get(first_symbol) is None:
                raise WorkflowException("%s is not defined" % first_symbol)

            return next_seg(first_symbol, ex[first_symbol_end:-1], obj[first_symbol])
        except WorkflowException as werr:
            expression_parse_exception = werr
        else:
            expression_parse_succeeded = True

    if fullJS and not expression_parse_succeeded:
        return execjs(
            ex,
            jslib,
            timeout,
            force_docker_pull=force_docker_pull,
            debug=debug,
            js_console=js_console,
        )
    else:
        if expression_parse_exception is not None:
            raise JavascriptException(
                "Syntax error in parameter reference '%s': %s. This could be "
                "due to using Javascript code without specifying "
                "InlineJavascriptRequirement." % (ex[1:-1], expression_parse_exception)
            )
        else:
            raise JavascriptException(
                "Syntax error in parameter reference '%s'. This could be due "
                "to using Javascript code without specifying "
                "InlineJavascriptRequirement." % ex
            )


def interpolate(
    scan,  # type: str
    rootvars,  # type: Dict[str, Any]
    timeout=default_timeout,  # type: float
    fullJS=False,  # type: bool
    jslib="",  # type: str
    force_docker_pull=False,  # type: bool
    debug=False,  # type: bool
    js_console=False,  # type: bool
    strip_whitespace=True,  # type: bool
):  # type: (...) -> JSON
    if strip_whitespace:
        scan = scan.strip()
    parts = []
    w = scanner(scan)
    while w:
        parts.append(scan[0 : w[0]])

        if scan[w[0]] == "$":
            e = evaluator(
                scan[w[0] + 1 : w[1]],
                jslib,
                rootvars,
                timeout,
                fullJS=fullJS,
                force_docker_pull=force_docker_pull,
                debug=debug,
                js_console=js_console,
            )
            if w[0] == 0 and w[1] == len(scan) and len(parts) <= 1:
                return e
            leaf = json_dumps(e, sort_keys=True)
            if leaf[0] == '"':
                leaf = leaf[1:-1]
            parts.append(leaf)
        elif scan[w[0]] == "\\":
            e = scan[w[1] - 1]
            parts.append(e)

        scan = scan[w[1] :]
        w = scanner(scan)
    parts.append(scan)
    return "".join(parts)


def needs_parsing(snippet):  # type: (Any) -> bool
    return isinstance(snippet, str) and ("$(" in snippet or "${" in snippet)


def do_eval(
    ex,  # type: Union[str, Dict[str, str]]
    jobinput,  # type: Dict[str, JSON]
    requirements,  # type: List[Dict[str, Any]]
    outdir,  # type: Optional[str]
    tmpdir,  # type: Optional[str]
    resources,  # type: Dict[str, int]
    context=None,  # type: Any
    timeout=default_timeout,  # type: float
    force_docker_pull=False,  # type: bool
    debug=False,  # type: bool
    js_console=False,  # type: bool
    strip_whitespace=True,  # type: bool
):  # type: (...) -> Any

    runtime = copy.deepcopy(resources)  # type: Dict[str, Any]
    runtime["tmpdir"] = docker_windows_path_adjust(tmpdir) if tmpdir else None
    runtime["outdir"] = docker_windows_path_adjust(outdir) if outdir else None

    rootvars = {"inputs": jobinput, "self": context, "runtime": runtime}

    # TODO: need to make sure the `rootvars dict`
    # contains no bytes type in the first place.
    rootvars = bytes2str_in_dicts(rootvars)  # type: ignore

    if isinstance(ex, str) and needs_parsing(ex):
        fullJS = False
        jslib = ""
        for r in reversed(requirements):
            if r["class"] == "InlineJavascriptRequirement":
                fullJS = True
                jslib = jshead(r.get("expressionLib", []), rootvars)
                break

        try:
            return interpolate(
                ex,
                rootvars,
                timeout=timeout,
                fullJS=fullJS,
                jslib=jslib,
                force_docker_pull=force_docker_pull,
                debug=debug,
                js_console=js_console,
                strip_whitespace=strip_whitespace,
            )

        except Exception as e:
            raise WorkflowException("Expression evaluation error:\n%s" % str(e)) from e
    else:
        return ex
