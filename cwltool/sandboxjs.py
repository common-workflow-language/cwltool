import errno
import json
import logging
import os
import select
import subprocess
import threading
from io import BytesIO
from typing import Any, Dict, List, Mapping, Text, Tuple, Union

from pkg_resources import resource_stream


class JavascriptException(Exception):
    pass


_logger = logging.getLogger("cwltool")

JSON = Union[Dict[Text, Any], List[Any], Text, int, float, bool, None]

localdata = threading.local()

have_node_slim = False
# minimum acceptable version of nodejs engine
minimum_node_version_str = '0.10.26'

def check_js_threshold_version(working_alias):
    # type: (str) -> bool

    """Checks if the nodeJS engine version on the system
    with the allowed minimum version.
    https://github.com/nodejs/node/blob/master/CHANGELOG.md#nodejs-changelog
    """
    # parse nodejs version into int Tuple: 'v4.2.6\n' -> [4, 2, 6]
    current_version_str = subprocess.check_output(
        [working_alias, "-v"]).decode('ascii')

    current_version = [int(v) for v in current_version_str.strip().strip('v').split('.')]
    minimum_node_version = [int(v) for v in minimum_node_version_str.split('.')]

    if current_version >= minimum_node_version:
        return True
    else:
        return False


def new_js_proc():
    # type: () -> subprocess.Popen

    res = resource_stream(__name__, 'cwlNodeEngine.js')
    nodecode = res.read()

    required_node_version, docker = (False,)*2
    nodejs = None
    trynodes = ("nodejs", "node")
    for n in trynodes:
        try:
            if subprocess.check_output([n, "--eval", "process.stdout.write('t')"]) != "t":
                continue
            else:
                nodejs = subprocess.Popen([n, "--eval", nodecode],
                                          stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)

                required_node_version = check_js_threshold_version(n)
                break
        except subprocess.CalledProcessError:
            pass
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise

    if nodejs is None or nodejs is not None and required_node_version is False:
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
            docker = True
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise
        except subprocess.CalledProcessError:
            pass

    # docker failed and nodejs not on system
    if nodejs is None:
        raise JavascriptException(
            u"cwltool requires Node.js engine to evaluate Javascript "
            "expressions, but couldn't find it.  Tried %s, docker run "
            "node:slim" % u", ".join(trynodes))

    # docker failed, but nodejs is installed on system but the version is below the required version
    if docker is False and required_node_version is False:
        raise JavascriptException(
            u'cwltool requires minimum v{} version of Node.js engine.'.format(minimum_node_version_str),
            u'Try updating: https://docs.npmjs.com/getting-started/installing-node')

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
