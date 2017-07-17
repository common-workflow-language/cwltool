from __future__ import absolute_import
import errno
import json
import logging
import os
import select
import subprocess
import threading
import sys
from io import BytesIO
from typing import Any, Dict, List, Mapping, Text, Tuple, Union
from .utils import onWindows
from pkg_resources import resource_stream

import six

try:
    import queue  # type: ignore
except ImportError:
    import Queue as queue  # type: ignore

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
                dockerimgs = subprocess.check_output(["docker", "images", nodeimg]).decode('utf-8')
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

    if not hasattr(localdata, "proc") or localdata.proc.poll() is not None or onWindows():
        localdata.proc = new_js_proc()

    nodejs = localdata.proc

    fn = u"\"use strict\";\n%s\n(function()%s)()" %\
         (jslib, js if isinstance(js, six.string_types) and len(js) > 1 and js[0] == '{' else ("{return (%s);}" % js))

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

    stdin_buf = BytesIO((json.dumps(fn) + "\n").encode('utf-8'))
    stdout_buf = BytesIO()
    stderr_buf = BytesIO()

    rselect = [nodejs.stdout, nodejs.stderr]  # type: List[BytesIO]
    wselect = [nodejs.stdin]  # type: List[BytesIO]

    # On windows system standard input/output are not handled properly by select  module(modules like  pywin32, msvcrt, gevent don't work either)
    if sys.platform=='win32':
        READ_BYTES_SIZE = 512

        # creating queue for reading from a thread to queue
        input_queue = queue.Queue()
        output_queue = queue.Queue()
        error_queue = queue.Queue()

        # To tell threads that output has ended and threads can safely exit
        no_more_output = threading.Lock()
        no_more_output.acquire()
        no_more_error = threading.Lock()
        no_more_error.acquire()

        # put constructed command to input queue which then will be passed to nodejs's stdin
        def put_input(input_queue):
            while True:
                b = stdin_buf.read(READ_BYTES_SIZE)
                if b:
                    input_queue.put(b)
                else:
                    break

        # get the output from nodejs's stdout and continue till otuput ends
        def get_output(output_queue):
            while not no_more_output.acquire(False):
                b=os.read(nodejs.stdout.fileno(), READ_BYTES_SIZE)
                if b:
                    output_queue.put(b)

        # get the output from nodejs's stderr and continue till error output ends
        def get_error(error_queue):
            while not no_more_error.acquire(False):
                b = os.read(nodejs.stderr.fileno(), READ_BYTES_SIZE)
                if b:
                    error_queue.put(b)

        # Threads managing nodejs.stdin, nodejs.stdout and nodejs.stderr respectively
        input_thread = threading.Thread(target=put_input, args=(input_queue,))
        input_thread.daemon=True
        input_thread.start()
        output_thread = threading.Thread(target=get_output, args=(output_queue,))
        output_thread.daemon=True
        output_thread.start()
        error_thread = threading.Thread(target=get_error, args=(error_queue,))
        error_thread.daemon=True
        error_thread.start()

        # mark if output/error is ready
        output_ready=False
        error_ready=False

        while (len(wselect) + len(rselect)) > 0:
            try:
                if nodejs.stdin in wselect:
                    if not input_queue.empty():
                        os.write(nodejs.stdin.fileno(), input_queue.get())
                    elif not input_thread.is_alive():
                        wselect = []
                if nodejs.stdout in rselect:
                    if not output_queue.empty():
                        output_ready = True
                        stdout_buf.write(output_queue.get())
                    elif output_ready:
                        rselect = []
                        no_more_output.release()
                        no_more_error.release()
                        output_thread.join()

                if nodejs.stderr in rselect:
                    if not error_queue.empty():
                        error_ready = True
                        stderr_buf.write(error_queue.get())
                    elif error_ready:
                        rselect = []
                        no_more_output.release()
                        no_more_error.release()
                        output_thread.join()
                        error_thread.join()
                if stdout_buf.getvalue().endswith("\n"):
                    rselect = []
                    no_more_output.release()
                    no_more_error.release()
                    output_thread.join()
            except OSError as e:
                break

    else:
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
                if stdout_buf.getvalue().endswith("\n".encode()):
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

    def stdfmt(data):  # type: (Text) -> Text
        if "\n" in data:
            return "\n" + data.strip()
        return data

    nodejs.poll()

    if debug:
        info = u"returncode was: %s\nscript was:\n%s\nstdout was: %s\nstderr was: %s\n" %\
               (nodejs.returncode, fn_linenum(), stdfmt(stdoutdata.decode('utf-8')), stdfmt(stderrdata.decode('utf-8')))
    else:
        info = stdfmt(stderrdata.decode('utf-8'))

    if nodejs.poll() not in (None, 0):
        if killed:
            raise JavascriptException(u"Long-running script killed after %s seconds: %s" % (timeout, info))
        else:
            raise JavascriptException(info)
    else:
        try:
            # On windows currently a new instance of nodejs process is used due to problem with blocking on read operation on windows
            if onWindows():
                nodejs.kill()
            return json.loads(stdoutdata.decode('utf-8'))
        except ValueError as e:
            raise JavascriptException(u"%s\nscript was:\n%s\nstdout was: '%s'\nstderr was: '%s'\n" %
                                      (e, fn_linenum(), stdoutdata, stderrdata))
