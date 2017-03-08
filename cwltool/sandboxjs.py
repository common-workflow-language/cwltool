import errno
import json
import logging
import os
import select
import subprocess
import threading
from io import BytesIO

from pkg_resources import resource_stream
from typing import Any, Dict, List, Mapping, Text, Union

class JavascriptException(Exception):
    pass


_logger = logging.getLogger("cwltool")

JSON = Union[Dict[Text, Any], List[Any], Text, int, float, bool, None]

localdata = threading.local()

have_node_slim = False


def new_js_proc():
    # type: () -> subprocess.Popen

    res = resource_stream(__name__, 'cwlNodeEngine.js')
    nodecode = res.read()

    nodejs = None
    trynodes = ("nodejs", "node")
    for n in trynodes:
        try:
            if subprocess.check_output([n, "--eval", "process.stdout.write('t')"]) != "t":
                continue
            nodejs = subprocess.Popen([n, "--eval", nodecode],
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
            break
        except subprocess.CalledProcessError:
            pass
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
                dockerimgs = subprocess.check_output(["docker", "images", nodeimg])
                if len(dockerimgs.split("\n")) <= 1:
                    nodejsimg = subprocess.check_output(["docker", "pull", nodeimg])
                    _logger.info("Pulled Docker image %s %s", nodeimg, nodejsimg)
                have_node_slim = True
            nodejs = subprocess.Popen(["docker", "run",
                                       "--attach=STDIN", "--attach=STDOUT", "--attach=STDERR",
                                       "--sig-proxy=true", "--interactive",
                                       "--rm", nodeimg, "node", "--eval", nodecode],
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

    return nodejs


def execjs(js, jslib, timeout=None, debug=False):  # type: (Union[Mapping, Text], Any, int, bool) -> JSON

    if not hasattr(localdata, "proc") or localdata.proc.poll() is not None:
        localdata.proc = new_js_proc()

    nodejs = localdata.proc

    fn = u"\"use strict\";\n%s\n(function()%s)()" %\
         (jslib, js if isinstance(js, basestring) and len(js) > 1 and js[0] == '{' else ("{return (%s);}" % js))

    killed = []

    def term():
        try:
            killed.append(True)
            nodejs.kill()
        except OSError:
            pass

    if timeout is None:
        timeout = 20

    tm = threading.Timer(timeout, term)
    tm.start()

    stdin_buf = BytesIO(json.dumps(fn) + "\n")
    stdout_buf = BytesIO()
    stderr_buf = BytesIO()

    rselect = [nodejs.stdout, nodejs.stderr]  # type: List[BytesIO]
    wselect = [nodejs.stdin]  # type: List[BytesIO]
    while (len(wselect) + len(rselect)) > 0:
        rready, wready, _ = select.select(rselect, wselect, [])
        try:
            if nodejs.stdin in wready:
                b = stdin_buf.read(select.PIPE_BUF)
                if b:
                    os.write(nodejs.stdin.fileno(), b)
                else:
                    wselect = []
            for pipes in ((nodejs.stdout, stdout_buf), (nodejs.stderr, stderr_buf)):
                if pipes[0] in rready:
                    b = os.read(pipes[0].fileno(), select.PIPE_BUF)
                    if b:
                        pipes[1].write(b)
                    else:
                        rselect.remove(pipes[0])
            if stdout_buf.getvalue().endswith("\n"):
                rselect = []
        except OSError as e:
            break
    tm.cancel()

    stdin_buf.close()
    stdoutdata = stdout_buf.getvalue()
    stderrdata = stderr_buf.getvalue()

    def fn_linenum():  # type: () -> Text
        lines = fn.splitlines()
        ofs = 0
        maxlines = 99
        if len(lines) > maxlines:
            ofs = len(lines) - maxlines
            lines = lines[-maxlines:]
        return u"\n".join(u"%02i %s" % (i + ofs + 1, b) for i, b in enumerate(lines))

    def stdfmt(data):  # type: (unicode) -> unicode
        if "\n" in data:
            return "\n" + data.strip()
        return data

    nodejs.poll()

    if debug:
        info = u"returncode was: %s\nscript was:\n%s\nstdout was: %s\nstderr was: %s\n" %\
               (nodejs.returncode, fn_linenum(), stdfmt(stdoutdata), stdfmt(stderrdata))
    else:
        info = stdfmt(stderrdata)

    if nodejs.poll() not in (None, 0):
        if killed:
            raise JavascriptException(u"Long-running script killed after %s seconds: %s" % (timeout, info))
        else:
            raise JavascriptException(info)
    else:
        try:
            return json.loads(stdoutdata)
        except ValueError as e:
            raise JavascriptException(u"%s\nscript was:\n%s\nstdout was: '%s'\nstderr was: '%s'\n" %
                                      (e, fn_linenum(), stdoutdata, stderrdata))
