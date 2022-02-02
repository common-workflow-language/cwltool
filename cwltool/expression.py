"""Parse CWL expressions."""

import copy
import json
import re
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    Optional,
    Tuple,
    Union,
    cast,
)

from schema_salad.utils import json_dumps

from .errors import WorkflowException
from .loghandler import _logger
from .sandboxjs import JavascriptException, default_timeout, execjs
from .utils import CWLObjectType, CWLOutputType, bytes2str_in_dicts


def jshead(engine_config: List[str], rootvars: CWLObjectType) -> str:
    # make sure all the byte strings are converted
    # to str in `rootvars` dict.

    return "\n".join(
        engine_config
        + [f"var {k} = {json_dumps(v, indent=4)};" for k, v in rootvars.items()]
    )


# decode all raw strings to unicode
seg_symbol = r"""\w+"""
seg_single = r"""\['([^']|\\')+'\]"""
seg_double = r"""\["([^"]|\\")+"\]"""
seg_index = r"""\[[0-9]+\]"""
segments = rf"(\.{seg_symbol}|{seg_single}|{seg_double}|{seg_index})"
segment_re = re.compile(segments, flags=re.UNICODE)
param_str = rf"\(({seg_symbol}){segments}*\)$"
param_re = re.compile(param_str, flags=re.UNICODE)


class SubstitutionError(Exception):
    pass


def scanner(scan: str) -> Optional[Tuple[int, int]]:
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
                return (i - 1, i + 1)
        elif state == DOLLAR:
            if c == "(":
                start = i - 1
                stack.append(PAREN)
            elif c == "{":
                start = i - 1
                stack.append(BRACE)
            else:
                stack.pop()
                i -= 1
        elif state == PAREN:
            if c == "(":
                stack.append(PAREN)
            elif c == ")":
                stack.pop()
                if stack[-1] == DOLLAR:
                    return (start, i + 1)
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
                    return (start, i + 1)
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

    if len(stack) > 1 and not (len(stack) == 2 and stack[1] in (BACKSLASH, DOLLAR)):
        raise SubstitutionError(
            "Substitution error, unfinished block starting at position {}: '{}' stack was {}".format(
                start, scan[start:], stack
            )
        )
    return None


def next_seg(
    parsed_string: str, remaining_string: str, current_value: CWLOutputType
) -> CWLOutputType:
    if remaining_string:
        m = segment_re.match(remaining_string)
        if not m:
            return current_value
        next_segment_str = m.group(1)

        key = None  # type: Optional[Union[str, int]]
        if next_segment_str[0] == ".":
            key = next_segment_str[1:]
        elif next_segment_str[1] in ("'", '"'):
            key = next_segment_str[2:-2].replace("\\'", "'").replace('\\"', '"')

        if key is not None:
            if (
                isinstance(current_value, MutableSequence)
                and key == "length"
                and not remaining_string[m.end(1) :]
            ):
                return len(current_value)
            if not isinstance(current_value, MutableMapping):
                raise WorkflowException(
                    "%s is a %s, cannot index on string '%s'"
                    % (parsed_string, type(current_value).__name__, key)
                )
            if key not in current_value:
                raise WorkflowException(f"{parsed_string} does not contain key '{key}'")
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
                    remaining_string[m.end(1) :],
                    cast(CWLOutputType, current_value[cast(str, key)]),
                )
            except KeyError:
                raise WorkflowException(f"{parsed_string} doesn't have property {key}")
        elif isinstance(current_value, list) and isinstance(key, int):
            try:
                return next_seg(
                    parsed_string + remaining_string,
                    remaining_string[m.end(1) :],
                    current_value[key],
                )
            except KeyError:
                raise WorkflowException(f"{parsed_string} doesn't have property {key}")
        else:
            raise WorkflowException(f"{parsed_string} doesn't have property {key}")
    else:
        return current_value


def evaluator(
    ex: str,
    jslib: str,
    obj: CWLObjectType,
    timeout: float,
    fullJS: bool = False,
    force_docker_pull: bool = False,
    debug: bool = False,
    js_console: bool = False,
    container_engine: str = "docker",
) -> Optional[CWLOutputType]:
    match = param_re.match(ex)

    expression_parse_exception = None

    if match is not None:
        first_symbol = match.group(1)
        first_symbol_end = match.end(1)

        if first_symbol_end + 1 == len(ex) and first_symbol == "null":
            return None
        try:
            if first_symbol not in obj:
                raise WorkflowException("%s is not defined" % first_symbol)

            return next_seg(
                first_symbol,
                ex[first_symbol_end:-1],
                cast(CWLOutputType, obj[first_symbol]),
            )
        except WorkflowException as werr:
            expression_parse_exception = werr

    if fullJS:
        return execjs(
            ex,
            jslib,
            timeout,
            force_docker_pull=force_docker_pull,
            debug=debug,
            js_console=js_console,
            container_engine=container_engine,
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


def _convert_dumper(string: str) -> str:
    return f"{json.dumps(string)} + "


def interpolate(
    scan: str,
    rootvars: CWLObjectType,
    timeout: float = default_timeout,
    fullJS: bool = False,
    jslib: str = "",
    force_docker_pull: bool = False,
    debug: bool = False,
    js_console: bool = False,
    strip_whitespace: bool = True,
    escaping_behavior: int = 2,
    convert_to_expression: bool = False,
    container_engine: str = "docker",
) -> Optional[CWLOutputType]:
    """
    Interpolate and evaluate.

    Note: only call with convert_to_expression=True on CWL Expressions in $()
    form that need interpolation.
    """
    if strip_whitespace:
        scan = scan.strip()
    parts = []
    if convert_to_expression:
        dump = _convert_dumper
        parts.append("${return ")
    else:
        dump = lambda x: x
    w = scanner(scan)
    while w:
        if convert_to_expression:
            parts.append(f'"{scan[0 : w[0]]}" + ')
        else:
            parts.append(scan[0 : w[0]])

        if scan[w[0]] == "$":
            if not convert_to_expression:
                e = evaluator(
                    scan[w[0] + 1 : w[1]],
                    jslib,
                    rootvars,
                    timeout,
                    fullJS=fullJS,
                    force_docker_pull=force_docker_pull,
                    debug=debug,
                    js_console=js_console,
                    container_engine=container_engine,
                )
                if w[0] == 0 and w[1] == len(scan) and len(parts) <= 1:
                    return e

                leaf = json_dumps(e, sort_keys=True)
                if leaf[0] == '"':
                    leaf = json.loads(leaf)
                parts.append(leaf)
            else:
                parts.append(
                    "function(){var item ="
                    + scan[w[0] : w[1]][2:-1]
                    + '; if (typeof(item) === "string"){ return item; } else { return JSON.stringify(item); }}() + '
                )
        elif scan[w[0]] == "\\":
            if escaping_behavior == 1:
                # Old behavior.  Just skip the next character.
                e = scan[w[1] - 1]
                parts.append(dump(e))
            elif escaping_behavior == 2:
                # Backslash quoting requires a three character lookahead.
                e = scan[w[0] : w[1] + 1]
                if e in ("\\$(", "\\${"):
                    # Suppress start of a parameter reference, drop the
                    # backslash.
                    parts.append(dump(e[1:]))
                    w = (w[0], w[1] + 1)
                elif e[1] == "\\":
                    # Double backslash, becomes a single backslash
                    parts.append(dump("\\"))
                else:
                    # Some other text, add it as-is (including the
                    # backslash) and resume scanning.
                    parts.append(dump(e[:2]))
            else:
                raise Exception("Unknown escaping behavior %s" % escaping_behavior)
        scan = scan[w[1] :]
        w = scanner(scan)
    if convert_to_expression:
        parts.append(f'"{scan}"')
        parts.append(";}")
    else:
        parts.append(scan)
    return "".join(parts)


def needs_parsing(snippet: Any) -> bool:
    return isinstance(snippet, str) and ("$(" in snippet or "${" in snippet)


def do_eval(
    ex: Optional[CWLOutputType],
    jobinput: CWLObjectType,
    requirements: List[CWLObjectType],
    outdir: Optional[str],
    tmpdir: Optional[str],
    resources: Dict[str, Union[float, int]],
    context: Optional[CWLOutputType] = None,
    timeout: float = default_timeout,
    force_docker_pull: bool = False,
    debug: bool = False,
    js_console: bool = False,
    strip_whitespace: bool = True,
    cwlVersion: str = "",
    container_engine: str = "docker",
) -> Optional[CWLOutputType]:

    runtime = cast(MutableMapping[str, Union[int, str, None]], copy.deepcopy(resources))
    runtime["tmpdir"] = tmpdir if tmpdir else None
    runtime["outdir"] = outdir if outdir else None

    rootvars = cast(
        CWLObjectType,
        bytes2str_in_dicts({"inputs": jobinput, "self": context, "runtime": runtime}),
    )

    if isinstance(ex, str) and needs_parsing(ex):
        fullJS = False
        jslib = ""
        for r in reversed(requirements):
            if r["class"] == "InlineJavascriptRequirement":
                fullJS = True
                jslib = jshead(cast(List[str], r.get("expressionLib", [])), rootvars)
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
                escaping_behavior=1
                if cwlVersion
                in (
                    "v1.0",
                    "v1.1.0-dev1",
                    "v1.1",
                    "v1.2.0-dev1",
                    "v1.2.0-dev2",
                    "v1.2.0-dev3",
                )
                else 2,
                container_engine=container_engine,
            )

        except Exception as e:
            _logger.exception(e)
            raise WorkflowException("Expression evaluation error:\n%s" % str(e)) from e
    else:
        return ex
