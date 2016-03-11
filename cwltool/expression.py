import subprocess
import json
from .aslist import aslist
import logging
from .errors import WorkflowException
import schema_salad.ref_resolver
from . import sandboxjs
import re
import typing

_logger = logging.getLogger("cwltool")


def jshead(engineConfig, rootvars):
    return "\n".join(engineConfig + ["var %s = %s;" %
                                     (k, json.dumps(v))
                                     for k, v in rootvars.items()])


seg_symbol = r"""\w+"""
seg_single = r"""\['([^']|\\')+'\]"""
seg_double = r"""\["([^"]|\\")+"\]"""
seg_index = r"""\[[0-9]+\]"""
segments = r"(\.%s|%s|%s|%s)" % (seg_symbol, seg_single, seg_double, seg_index)
segment_re = re.compile(segments, flags=re.UNICODE)
param_re = re.compile(r"\$\((%s)%s*\)" %
                      (seg_symbol, segments), flags=re.UNICODE)


def next_seg(remain, obj):
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


def param_interpolate(ex, obj, strip=True):
    m = param_re.search(ex)
    if m:
        leaf = next_seg(m.group(0)[m.end(1) - m.start(0):-1], obj[m.group(1)])
        if strip and len(ex.strip()) == len(m.group(0)):
            return leaf
        else:
            leaf = json.dumps(leaf, sort_keys=True)
            if leaf[0] == '"':
                leaf = leaf[1:-1]
            return ex[0:m.start(0)] + leaf + param_interpolate(
                ex[m.end(0):], obj, False)
    else:
        if "$(" in ex or "${" in ex:
            _logger.warn(
                "Warning possible workflow bug: found '$(' or '${' in '%s' "
                "but did not match valid parameter reference and "
                "InlineJavascriptRequirement not specified.", ex)
        return ex


def do_eval(ex, jobinput, requirements, outdir, tmpdir, resources,
            context=None, pull_image=True, timeout=None):
    runtime = resources.copy()
    runtime["tmpdir"] = tmpdir
    runtime["outdir"] = outdir

    rootvars = {
        "inputs": jobinput,
        "self": context,
        "runtime": runtime
    }

    if isinstance(ex, basestring):
        for r in requirements:
            if r["class"] == "InlineJavascriptRequirement":
                return sandboxjs.interpolate(
                    ex, jshead(r.get("expressionLib", []), rootvars),
                    timeout=timeout)
        return param_interpolate(ex, rootvars)
    return ex
