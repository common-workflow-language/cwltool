import subprocess
import json
import logging
import os
import re

from typing import Any, AnyStr, Union
import schema_salad.validate as validate
import schema_salad.ref_resolver

from .utils import aslist, get_feature
from .errors import WorkflowException
from . import sandboxjs
from . import docker

_logger = logging.getLogger("cwltool")

def jshead(engineConfig, rootvars):
    # type: (List[unicode],Dict[str,str]) -> unicode
    return u"\n".join(engineConfig + [u"var %s = %s;" % (k, json.dumps(v, indent=4)) for k, v in rootvars.items()])

seg_symbol = r"""\w+"""
seg_single = r"""\['([^']|\\')+'\]"""
seg_double = r"""\["([^"]|\\")+"\]"""
seg_index = r"""\[[0-9]+\]"""
segments = r"(\.%s|%s|%s|%s)" % (seg_symbol, seg_single, seg_double, seg_index)
segment_re = re.compile(segments, flags=re.UNICODE)
param_re = re.compile(r"\((%s)%s*\)$" % (seg_symbol, segments), flags=re.UNICODE)

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
            if c == '$':
                stack.append(DOLLAR)
            elif c == '\\':
                stack.append(BACKSLASH)
        elif state == BACKSLASH:
            stack.pop()
            if stack[-1] == DEFAULT:
                return [i-1, i+1]
        elif state == DOLLAR:
            if c == '(':
                start = i-1
                stack.append(PAREN)
            elif c == '{':
                start = i-1
                stack.append(BRACE)
            else:
                stack.pop()
        elif state == PAREN:
            if c == '(':
                stack.append(PAREN)
            elif c == ')':
                stack.pop()
                if stack[-1] == DOLLAR:
                    return [start, i+1]
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
                    return [start, i+1]
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
        raise SubstitutionError("Substitution error, unfinished block starting at position {}: {}".format(start, scan[start:]))
    else:
        return None

def next_seg(remain, obj):  # type: (str,Any)->str
    if remain:
        m = segment_re.match(remain)
        if m.group(0)[0] == '.':
            return next_seg(remain[m.end(0):], obj[m.group(0)[1:]])
        elif m.group(0)[1] in ("'", '"'):
            key = m.group(0)[2:-2].replace("\\'", "'").replace('\\"', '"')
            return next_seg(remain[m.end(0):], obj[key])
        else:
            key = m.group(0)[1:-1]
            return next_seg(remain[m.end(0):], obj[int(key)])
    else:
        return obj

def evaluator(ex, jslib, obj, fullJS=False, timeout=None):
    # type: (str, Dict[Any,Any], bool) -> Union[str, unicode]
    m = param_re.match(ex)
    if m:
        return next_seg(m.group(0)[m.end(1) - m.start(0):-1], obj[m.group(1)])
    elif fullJS:
        return sandboxjs.execjs(ex, jslib, timeout=timeout)
    else:
        raise JavascriptException("Syntax error in parameter reference '%s' or used Javascript code without specifying InlineJavascriptRequirement.", ex)

def interpolate(scan, jslib, rootvars,
                timeout=None, fullJS=None):
    # type: (str, Union[str, unicode], int, bool) -> JSON
    scan = scan.strip()
    parts = []
    w = scanner(scan)
    while w:
        parts.append(scan[0:w[0]])

        if scan[w[0]] == '$':
            e = evaluator(scan[w[0]+1:w[1]], jslib, rootvars, fullJS=fullJS,
                          timeout=timeout)
            if w[0] == 0 and w[1] == len(scan):
                return e
            leaf = json.dumps(e, sort_keys=True)
            if leaf[0] == '"':
                leaf = leaf[1:-1]
            parts.append(leaf)
        elif scan[w[0]] == '\\':
            e = scan[w[1]-1]
            parts.append(e)

        scan = scan[w[1]:]
        w = scanner(scan)
    parts.append(scan)
    return ''.join(parts)

def do_eval(ex, jobinput, requirements, outdir, tmpdir, resources,
            context=None, pull_image=True, timeout=None):
    # type: (Union[dict, unicode], Dict[unicode, Union[Dict, List, unicode]], List[Dict[str, Any]], str, str, Dict[str, Union[int, str]], Any, bool, int) -> Any

    runtime = resources.copy()
    runtime["tmpdir"] = tmpdir
    runtime["outdir"] = outdir

    rootvars = {
        "inputs": jobinput,
        "self": context,
        "runtime": runtime }

    if isinstance(ex, (str, unicode)):
        fullJS = False
        jslib = ""
        for r in reversed(requirements):
            if r["class"] == "InlineJavascriptRequirement":
                fullJS = True
                jslib = jshead(r.get("expressionLib", []), rootvars)
                break

        return interpolate(unicode(ex),
                           jslib,
                           rootvars,
                           timeout=timeout,
                           fullJS=fullJS)
    else:
        return ex
