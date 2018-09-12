"""Parse CWL expressions."""
from __future__ import absolute_import

import copy
import re
from typing import (Any, Dict, List, MutableMapping, MutableSequence, Optional,
                    Union)

import six
from six import string_types, u
from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from . import sandboxjs
from .errors import WorkflowException
from .utils import bytes2str_in_dicts, docker_windows_path_adjust, json_dumps


def jshead(engine_config, rootvars):
    # type: (List[Text], Dict[Text, Any]) -> Text

    # make sure all the byte strings are converted
    # to str in `rootvars` dict.

    return u"\n".join(
        engine_config + [u"var {} = {};".format(k, json_dumps(v, indent=4))
                         for k, v in rootvars.items()])


# decode all raw strings to unicode
seg_symbol = r"""\w+"""
seg_single = r"""\['([^']|\\')+'\]"""
seg_double = r"""\["([^"]|\\")+"\]"""
seg_index = r"""\[[0-9]+\]"""
segments = r"(\.%s|%s|%s|%s)" % (seg_symbol, seg_single, seg_double, seg_index)
segment_re = re.compile(u(segments), flags=re.UNICODE)
param_str = r"\((%s)%s*\)$" % (seg_symbol, segments)
param_re = re.compile(u(param_str), flags=re.UNICODE)

JSON = Union[Dict[Any, Any], List[Any], Text, int, float, bool, None]


class SubstitutionError(Exception):
    pass


def scanner(scan):  # type: (Text) -> Optional[List[int]]
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
            if c == '$':
                stack.append(DOLLAR)
            elif c == '\\':
                stack.append(BACKSLASH)
        elif state == BACKSLASH:
            stack.pop()
            if stack[-1] == DEFAULT:
                return [i - 1, i + 1]
        elif state == DOLLAR:
            if c == '(':
                start = i - 1
                stack.append(PAREN)
            elif c == '{':
                start = i - 1
                stack.append(BRACE)
            else:
                stack.pop()
        elif state == PAREN:
            if c == '(':
                stack.append(PAREN)
            elif c == ')':
                stack.pop()
                if stack[-1] == DOLLAR:
                    return [start, i + 1]
            elif c == "'":
                stack.append(SINGLE_QUOTE)
            elif c == '"':
                stack.append(DOUBLE_QUOTE)
        elif state == BRACE:
            if c == '{':
                stack.append(BRACE)
            elif c == '}':
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
            elif c == '\\':
                stack.append(BACKSLASH)
        elif state == DOUBLE_QUOTE:
            if c == '"':
                stack.pop()
            elif c == '\\':
                stack.append(BACKSLASH)
        i += 1

    if len(stack) > 1:
        raise SubstitutionError(
            "Substitution error, unfinished block starting at position {}: {}".format(start, scan[start:]))
    else:
        return None


def next_seg(parsed_string, remaining_string, current_value):  # type: (Text, Text, Any) -> Any
    if remaining_string:
        m = segment_re.match(remaining_string)
        if not m:
            return current_value
        next_segment_str = m.group(0)

        key = None  # type: Optional[Union[Text, int]]
        if next_segment_str[0] == '.':
            key = next_segment_str[1:]
        elif next_segment_str[1] in ("'", '"'):
            key = next_segment_str[2:-2].replace("\\'", "'").replace('\\"', '"')

        if key:
            if isinstance(current_value, MutableSequence) and key == "length" and not remaining_string[m.end(0):]:
                return len(current_value)
            if not isinstance(current_value, MutableMapping):
                raise WorkflowException("%s is a %s, cannot index on string '%s'" % (parsed_string, type(current_value).__name__, key))
            if key not in current_value:
                raise WorkflowException("%s does not contain key '%s'" % (parsed_string, key))
        else:
            try:
                key = int(next_segment_str[1:-1])
            except ValueError as v:
                raise WorkflowException(u(str(v)))
            if not isinstance(current_value, MutableSequence):
                raise WorkflowException("%s is a %s, cannot index on int '%s'" % (parsed_string, type(current_value).__name__, key))
            if key >= len(current_value):
                raise WorkflowException("%s list index %i out of range" % (parsed_string, key))

        try:
            return next_seg(parsed_string + remaining_string, remaining_string[m.end(0):], current_value[key])
        except KeyError:
            raise WorkflowException("%s doesn't have property %s" % (parsed_string, key))
    else:
        return current_value


def evaluator(ex,                       # type: Text
              jslib,                    # type: Text
              obj,                      # type: Dict[Text, Any]
              fullJS=False,             # type: bool
              timeout=None,             # type: float
              force_docker_pull=False,  # type: bool
              debug=False,              # type: bool
              js_console=False          # type: bool
             ):
    # type: (...) -> JSON
    match = param_re.match(ex)

    expression_parse_exception = None
    expression_parse_succeeded = False

    if match:
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
        return sandboxjs.execjs(
            ex, jslib, timeout=timeout, force_docker_pull=force_docker_pull,
            debug=debug, js_console=js_console)
    else:
        if expression_parse_exception is not None:
            raise sandboxjs.JavascriptException(
                "Syntax error in parameter reference '%s': %s. This could be "
                "due to using Javascript code without specifying "
                "InlineJavascriptRequirement." % \
                    (ex[1:-1], expression_parse_exception))
        else:
            raise sandboxjs.JavascriptException(
                "Syntax error in parameter reference '%s'. This could be due "
                "to using Javascript code without specifying "
                "InlineJavascriptRequirement." % ex)


def interpolate(scan,                     # type: Text
                rootvars,                 # type: Dict[Text, Any]
                timeout=None,             # type: float
                fullJS=False,             # type: bool
                jslib="",                 # type: Text
                force_docker_pull=False,  # type: bool
                debug=False,              # type: bool
                js_console=False,         # type: bool
                strip_whitespace=True     # type: bool
               ):  # type: (...) -> JSON
    if strip_whitespace:
        scan = scan.strip()
    parts = []
    w = scanner(scan)
    while w:
        parts.append(scan[0:w[0]])

        if scan[w[0]] == '$':
            e = evaluator(scan[w[0] + 1:w[1]], jslib, rootvars, fullJS=fullJS,
                          timeout=timeout, force_docker_pull=force_docker_pull,
                          debug=debug, js_console=js_console)
            if w[0] == 0 and w[1] == len(scan) and len(parts) <= 1:
                return e
            leaf = json_dumps(e, sort_keys=True)
            if leaf[0] == '"':
                leaf = leaf[1:-1]
            parts.append(leaf)
        elif scan[w[0]] == '\\':
            e = scan[w[1] - 1]
            parts.append(e)

        scan = scan[w[1]:]
        w = scanner(scan)
    parts.append(scan)
    return ''.join(parts)

def needs_parsing(snippet):  # type: (Any) -> bool
    return isinstance(snippet, string_types) \
        and ("$(" in snippet or "${" in snippet)

def do_eval(ex,                       # type: Union[Text, Dict]
            jobinput,                 # type: Dict[Text, Union[Dict, List, Text, None]]
            requirements,             # type: List[Dict[Text, Any]]
            outdir,                   # type: Optional[Text]
            tmpdir,                   # type: Optional[Text]
            resources,                # type: Dict[str, int]
            context=None,             # type: Any
            timeout=None,             # type: float
            force_docker_pull=False,  # type: bool
            debug=False,              # type: bool
            js_console=False,         # type: bool
            strip_whitespace=True     # type: bool
           ):  # type: (...) -> Any

    runtime = copy.deepcopy(resources)  # type: Dict[str, Any]
    runtime["tmpdir"] = docker_windows_path_adjust(tmpdir)
    runtime["outdir"] = docker_windows_path_adjust(outdir)

    rootvars = {
        u"inputs": jobinput,
        u"self": context,
        u"runtime": runtime}

    # TODO: need to make sure the `rootvars dict`
    # contains no bytes type in the first place.
    if six.PY3:
        rootvars = bytes2str_in_dicts(rootvars)  # type: ignore

    if needs_parsing(ex):
        assert isinstance(ex, string_types)
        fullJS = False
        jslib = u""
        for r in reversed(requirements):
            if r["class"] == "InlineJavascriptRequirement":
                fullJS = True
                jslib = jshead(r.get("expressionLib", []), rootvars)
                break

        try:
            return interpolate(ex,
                               rootvars,
                               timeout=timeout,
                               fullJS=fullJS,
                               jslib=jslib,
                               force_docker_pull=force_docker_pull,
                               debug=debug,
                               js_console=js_console,
                               strip_whitespace=strip_whitespace)

        except Exception as e:
            raise WorkflowException("Expression evaluation error:\n%s" % e)
    else:
        return ex
