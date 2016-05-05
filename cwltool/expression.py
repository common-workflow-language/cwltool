from . import docker
import subprocess
import json
from .utils import aslist, get_feature
import logging
import os
from .errors import WorkflowException
import yaml
import schema_salad.validate as validate
import schema_salad.ref_resolver
from . import sandboxjs
import re
from typing import Any, AnyStr, Union

_logger = logging.getLogger("cwltool")

def jshead(engineConfig, rootvars):
    # type: (List[unicode],Dict[str,str]) -> unicode
    return u"\n".join(engineConfig + [u"var %s = %s;" % (k, json.dumps(v, indent=4)) for k, v in rootvars.items()])

def exeval(ex, jobinput, requirements, outdir, tmpdir, context, pull_image):
    # type: (Dict[str,Any], Dict[str,str], List[Dict[str, Any]], str, str, Any, bool) -> sandboxjs.JSON

    if ex["engine"] == "https://w3id.org/cwl/cwl#JavascriptEngine":
        engineConfig = []  # type: List[unicode]
        for r in reversed(requirements):
            if r["class"] == "ExpressionEngineRequirement" and r["id"] == "https://w3id.org/cwl/cwl#JavascriptEngine":
                engineConfig = r.get("engineConfig", [])
                break
        rootvars = {
            "inputs": jobinput,
            "self": context,
            "runtime": {
                "tmpdir": tmpdir,
                "outdir": outdir
                }
        }
        return sandboxjs.execjs(ex["script"], jshead(engineConfig, rootvars))

    for r in reversed(requirements):
        if r["class"] == "ExpressionEngineRequirement" and r["id"] == ex["engine"]:
            runtime = []  # type: List[str]

            class DR(object):
                def __init__(self):  # type: ()->None
                    self.requirements = None  # type: List[None]
                    self.hints = None  # type: List[None]
            dr = DR()
            dr.requirements = r.get("requirements", [])
            dr.hints = r.get("hints", [])

            (docker_req, docker_is_req) = get_feature(dr, "DockerRequirement")
            img_id = None
            if docker_req:
                img_id = docker.get_from_requirements(docker_req, docker_is_req, pull_image)
            if img_id:
                runtime = ["docker", "run", "-i", "--rm", img_id]

            inp = {
                "script": ex["script"],
                "engineConfig": r.get("engineConfig", []),
                "job": jobinput,
                "context": context,
                "outdir": outdir,
                "tmpdir": tmpdir,
            }

            _logger.debug(u"Invoking expression engine %s with %s",
                          runtime + aslist(r["engineCommand"]),
                                           json.dumps(inp, indent=4))

            sp = subprocess.Popen(runtime + aslist(r["engineCommand"]),
                             shell=False,
                             close_fds=True,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)

            (stdoutdata, stderrdata) = sp.communicate(json.dumps(inp) + "\n\n")
            if sp.returncode != 0:
                raise WorkflowException(u"Expression engine returned non-zero exit code on evaluation of\n%s" % json.dumps(inp, indent=4))

            return json.loads(stdoutdata)

    raise WorkflowException(u"Unknown expression engine '%s'" % ex["engine"])

seg_symbol = r"""\w+"""
seg_single = r"""\['([^']|\\')+'\]"""
seg_double = r"""\["([^"]|\\")+"\]"""
seg_index  = r"""\[[0-9]+\]"""
segments = r"(\.%s|%s|%s|%s)" % (seg_symbol, seg_single, seg_double, seg_index)
segment_re = re.compile(segments, flags=re.UNICODE)
param_re = re.compile(r"\$\((%s)%s*\)" % (seg_symbol, segments), flags=re.UNICODE)

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


def param_interpolate(ex, obj, strip=True):
    # type: (str, Dict[Any,Any], bool) -> Union[str, unicode]
    m = param_re.search(ex)
    if m:
        leaf = next_seg(m.group(0)[m.end(1) - m.start(0):-1], obj[m.group(1)])
        if strip and len(ex.strip()) == len(m.group(0)):
            return leaf
        else:
            leaf = json.dumps(leaf, sort_keys=True)
            if leaf[0] == '"':
                leaf = leaf[1:-1]
            return ex[0:m.start(0)] + leaf + param_interpolate(ex[m.end(0):], obj, False)
    else:
        if "$(" in ex or "${" in ex:
            _logger.warn(u"Warning possible workflow bug: found '$(' or '${' in '%s' but did not match valid parameter reference and InlineJavascriptRequirement not specified.", ex)
        return ex


def do_eval(ex, jobinput, requirements, outdir, tmpdir, resources,
            context=None, pull_image=True, timeout=None):
    # type: (Any, Dict[str,str], List[Dict[str,Any]], str, str, Dict[str, Union[int, str]], Any, bool, int) -> Any

    runtime = resources.copy()
    runtime["tmpdir"] = tmpdir
    runtime["outdir"] = outdir

    rootvars = {
            "inputs": jobinput,
            "self": context,
            "runtime": runtime
        }

    if isinstance(ex, dict) and "engine" in ex and "script" in ex:
        return exeval(ex, jobinput, requirements, outdir, tmpdir, context, pull_image)
    if isinstance(ex, basestring):
        for r in requirements:
            if r["class"] == "InlineJavascriptRequirement":
                return sandboxjs.interpolate(str(ex), jshead(r.get("expressionLib", []), rootvars),
                                             timeout=timeout)
        return param_interpolate(str(ex), rootvars)
    else:
        return ex
