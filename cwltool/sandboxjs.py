import subprocess
import json
import threading
import errno
import logging
from typing import Any, Dict, List, Mapping, Text, TypeVar, Union


class JavascriptException(Exception):
    pass

_logger = logging.getLogger("cwltool")

JSON = Union[Dict[Any,Any], List[Any], Text, int, long, float, bool, None]

have_node_slim = False

def execjs(js, jslib, timeout=None):  # type: (Union[Mapping, Text], Any, int) -> JSON
    nodejs = None
    trynodes = ("nodejs", "node")
    for n in trynodes:
        try:
            nodejs = subprocess.Popen([n], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            break
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise

    if nodejs is None:
        try:
            nodeimg = "node:slim"
            global have_node_slim
            if not have_node_slim:
                nodejsimg = subprocess.check_output(["docker", "pull", nodeimg])
                _logger.info("Pulled Docker image %s %s", nodeimg, nodejsimg)
                have_node_slim = True
            nodejs = subprocess.Popen(["docker", "run",
                                       "--attach=STDIN", "--attach=STDOUT", "--attach=STDERR",
                                       "--sig-proxy=true", "--interactive",
                                       "--rm", nodeimg],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise
        except subprocess.CalledProcessError:
            pass

    if nodejs is None:
        raise JavascriptException(
            u"cwltool requires Node.js engine to evaluate Javascript "
            "expressions, but couldn't find it.  Tried %s, docker run "
            "node:slim" % u", ".join(trynodes))

    fn = u"\"use strict\";\n%s\n(function()%s)()" % (jslib, js if isinstance(js, basestring) and len(js) > 1 and js[0] == '{' else ("{return (%s);}" % js))
    script = u"console.log(JSON.stringify(require(\"vm\").runInNewContext(%s, {})));\n" % json.dumps(fn)

    killed = []

    def term():
        try:
            nodejs.kill()
            killed.append(True)
        except OSError:
            pass

    if timeout is None:
        timeout = 20

    tm = threading.Timer(timeout, term)
    tm.start()

    stdoutdata, stderrdata = nodejs.communicate(script)
    tm.cancel()

    def fn_linenum():  # type: () -> Text
        return u"\n".join(u"%04i %s" % (i+1, b) for i, b in enumerate(fn.split("\n")))

    if killed:
        raise JavascriptException(u"Long-running script killed after %s seconds.\nscript was:\n%s\n" % (timeout, fn_linenum()))

    if nodejs.returncode != 0:
        raise JavascriptException(u"Returncode was: %s\nscript was:\n%s\nstdout was: '%s'\nstderr was: '%s'\n" % (nodejs.returncode, fn_linenum(), stdoutdata, stderrdata))
    else:
        try:
            return json.loads(stdoutdata)
        except ValueError as e:
            raise JavascriptException(u"%s\nscript was:\n%s\nstdout was: '%s'\nstderr was: '%s'\n" % (e, fn_linenum(), stdoutdata, stderrdata))
