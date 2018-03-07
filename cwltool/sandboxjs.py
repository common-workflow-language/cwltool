from __future__ import absolute_import
import errno
import json
import logging
import os
import re
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
        [working_alias, "-v"]).decode('utf-8')

    current_version = [int(v) for v in current_version_str.strip().strip('v').split('.')]
    minimum_node_version = [int(v) for v in minimum_node_version_str.split('.')]

    if current_version >= minimum_node_version:
        return True
    else:
        return False


def new_js_proc(force_docker_pull=False, js_console=False):
    # type: (bool, bool) -> subprocess.Popen
    
    cwl_node_engine_js = 'cwlNodeEngine.js'
    if js_console:
        cwl_node_engine_js = 'cwlNodeEngineJSConsole.js'
        _logger.warn("Running with support for javascript console in expressions (DO NOT USE IN PRODUCTION)")

    res = resource_stream(__name__, cwl_node_engine_js)
    nodecode = res.read().decode('utf-8')

    required_node_version, docker = (False,)*2
    nodejs = None
    trynodes = ("nodejs", "node")
    for n in trynodes:
        try:
            if subprocess.check_output([n, "--eval", "process.stdout.write('t')"]).decode('utf-8') != "t":
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
                dockerimgs = subprocess.check_output(["docker", "images", "-q", nodeimg]).decode('utf-8')
                # if output is an empty string
                if (len(dockerimgs.split("\n")) <= 1) or force_docker_pull:
                    # pull node:slim docker container
                    nodejsimg = subprocess.check_output(["docker", "pull", nodeimg]).decode('utf-8')
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


def execjs(js, jslib, timeout=None, force_docker_pull=False, debug=False, js_console=False):  # type: (Union[Mapping, Text], Any, int, bool, bool, bool) -> JSON

    if not hasattr(localdata, "proc") or localdata.proc.poll() is not None or onWindows():
        localdata.proc = new_js_proc(force_docker_pull=force_docker_pull, js_console=js_console)

    nodejs = localdata.proc

    fn = u"\"use strict\";\n%s\n(function()%s)()" %\
         (jslib, js if isinstance(js, six.string_types) and len(js) > 1 and js[0] == '{' else ("{return (%s);}" % js))

    killed = []

    """ Kill the node process if it exceeds timeout limit"""
    def terminate():
        try:
            killed.append(True)
            nodejs.kill()
        except OSError:
            pass

    if timeout is None:
        timeout = 20

    tm = threading.Timer(timeout, terminate)
    tm.start()

    stdin_buf = BytesIO((json.dumps(fn) + "\n").encode('utf-8'))
    stdout_buf = BytesIO()
    stderr_buf = BytesIO()

    rselect = [nodejs.stdout, nodejs.stderr]  # type: List[BytesIO]
    wselect = [nodejs.stdin]  # type: List[BytesIO]

    PROCESS_FINISHED_STR = "r1cepzbhUTxtykz5XTC4\n"

    def process_finished(): # type: () -> bool
        return stdout_buf.getvalue().decode().endswith(PROCESS_FINISHED_STR) and \
            stderr_buf.getvalue().decode().endswith(PROCESS_FINISHED_STR)

    # On windows system standard input/output are not handled properly by select module
    # (modules like  pywin32, msvcrt, gevent don't work either)
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

        finished = False

        while not finished and tm.is_alive():
            try:
                if nodejs.stdin in wselect:
                    if not input_queue.empty():
                        os.write(nodejs.stdin.fileno(), input_queue.get())
                    elif not input_thread.is_alive():
                        wselect = []
                if nodejs.stdout in rselect:
                    if not output_queue.empty():
                        stdout_buf.write(output_queue.get())

                if nodejs.stderr in rselect:
                    if not error_queue.empty():
                        stderr_buf.write(error_queue.get())                

                if process_finished() and error_queue.empty() and output_queue.empty():
                    finished = True
                    no_more_output.release()
                    no_more_error.release()
            except OSError as e:
                break

    else:
        while not process_finished() and tm.is_alive():
            rready, wready, _ = select.select(rselect, wselect, [])
            try:
                if nodejs.stdin in wready:
                    b = stdin_buf.read(select.PIPE_BUF)
                    if b:
                        os.write(nodejs.stdin.fileno(), b)
                for pipes in ((nodejs.stdout, stdout_buf), (nodejs.stderr, stderr_buf)):
                    if pipes[0] in rready:
                        b = os.read(pipes[0].fileno(), select.PIPE_BUF)
                        if b:
                            pipes[1].write(b)
            except OSError as e:
                break
    tm.cancel()

    stdin_buf.close()
    stdoutdata = stdout_buf.getvalue()[:-len(PROCESS_FINISHED_STR) - 1]
    stderrdata = stderr_buf.getvalue()[:-len(PROCESS_FINISHED_STR) - 1]

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

    if js_console:
        if len(stderrdata) > 0:
            _logger.info("Javascript console output:")
            _logger.info("----------------------------------------")
            _logger.info('\n'.join(re.findall(r'^[[](?:log|err)[]].*$', stderrdata.decode('utf-8'), flags=re.MULTILINE)))
            _logger.info("----------------------------------------")

    if debug:
        info = u"returncode was: %s\nscript was:\n%s\nstdout was: %s\nstderr was: %s\n" %\
               (nodejs.returncode, fn_linenum(), stdfmt(stdoutdata.decode('utf-8')), stdfmt(stderrdata.decode('utf-8')))
    else:
        info = u"Javascript expression was: %s\nstdout was: %s\nstderr was: %s" %\
               (js, stdfmt(stdoutdata.decode('utf-8')), stdfmt(stderrdata.decode('utf-8')))

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
