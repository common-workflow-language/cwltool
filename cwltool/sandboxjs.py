"""Evaluate CWL Javascript Expressions in a sandbox."""
from __future__ import absolute_import

import errno
import json
import os
import re
import select
import sys
import threading
from io import BytesIO
from typing import Any, Dict, List, Tuple, Union

import six
from pkg_resources import resource_stream
from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .loghandler import _logger
from .utils import json_dumps, onWindows, processes_to_kill, subprocess
try:
    import queue  # type: ignore
except ImportError:
    import Queue as queue  # type: ignore


class JavascriptException(Exception):
    pass


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

    return current_version >= minimum_node_version


def new_js_proc(js_text, force_docker_pull=False):
    # type: (Text, bool) -> subprocess.Popen

    required_node_version, docker = (False,)*2
    nodejs = None
    trynodes = ("nodejs", "node")
    for n in trynodes:
        try:
            if subprocess.check_output([n, "--eval", "process.stdout.write('t')"]).decode('utf-8') != "t":
                continue
            else:
                nodejs = subprocess.Popen([n, "--eval", js_text],
                                          stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
                processes_to_kill.append(nodejs)
                required_node_version = check_js_threshold_version(n)
                break
        except (subprocess.CalledProcessError, OSError):
            pass

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
                                       "--rm", nodeimg, "node", "--eval", js_text],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes_to_kill.append(nodejs)
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
            u"cwltool requires Node.js engine to evaluate and validate "
            u"Javascript expressions, but couldn't find it.  Tried {}, "
            u"docker run node:slim".format(u", ".join(trynodes)))

    # docker failed, but nodejs is installed on system but the version is below the required version
    if docker is False and required_node_version is False:
        raise JavascriptException(
            u'cwltool requires minimum v{} version of Node.js engine.'.format(
                minimum_node_version_str),
            u'Try updating: https://docs.npmjs.com/getting-started/installing-node')

    return nodejs

PROCESS_FINISHED_STR = "r1cepzbhUTxtykz5XTC4\n"

def exec_js_process(js_text,                  # type: Text
                    timeout=None,             # type: float
                    js_console=False,         # type: bool
                    context=None,             # type: Text
                    force_docker_pull=False,  # type: bool
                   ):
    # type: (...) -> Tuple[int, Text, Text]

    if not hasattr(localdata, "procs"):
        localdata.procs = {}

    if js_console and context is not None:
        raise NotImplementedError("js_console=True and context not implemented")

    if js_console:
        js_engine = 'cwlNodeEngineJSConsole.js'
        _logger.warning(
            "Running with support for javascript console in expressions (DO NOT USE IN PRODUCTION)")
    elif context is not None:
        js_engine = "cwlNodeEngineWithContext.js"
    else:
        js_engine = 'cwlNodeEngine.js'

    created_new_process = False

    if context is None:
        nodejs = localdata.procs.get(js_engine)
    else:
        nodejs = localdata.procs.get((js_engine, context))

    if nodejs is None \
            or nodejs.poll() is not None \
            or onWindows():
        res = resource_stream(__name__, js_engine)
        js_engine_code = res.read().decode('utf-8')

        created_new_process = True

        new_proc = new_js_proc(js_engine_code, force_docker_pull=force_docker_pull)

        if context is None:
            localdata.procs[js_engine] = new_proc
            nodejs = new_proc
        else:
            localdata.procs[(js_engine, context)] = new_proc
            nodejs = new_proc

    killed = []

    def terminate():
        """ Kill the node process if it exceeds timeout limit"""
        try:
            killed.append(True)
            nodejs.kill()
        except OSError:
            pass

    if timeout is None:
        timeout = 20

    timer = threading.Timer(timeout, terminate)
    timer.daemon = True
    timer.start()

    stdin_text = u""
    if created_new_process and context is not None:
        stdin_text = json_dumps(context) + "\n"
    stdin_text += json_dumps(js_text) + "\n"

    stdin_buf = BytesIO(stdin_text.encode('utf-8'))
    stdout_buf = BytesIO()
    stderr_buf = BytesIO()

    rselect = [nodejs.stdout, nodejs.stderr]  # type: List[BytesIO]
    wselect = [nodejs.stdin]  # type: List[BytesIO]


    def process_finished():  # type: () -> bool
        return stdout_buf.getvalue().decode('utf-8').endswith(PROCESS_FINISHED_STR) and \
            stderr_buf.getvalue().decode('utf-8').endswith(PROCESS_FINISHED_STR)

    # On windows system standard input/output are not handled properly by select module
    # (modules like  pywin32, msvcrt, gevent don't work either)
    if sys.platform == 'win32':
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
                buf = stdin_buf.read(READ_BYTES_SIZE)
                if buf:
                    input_queue.put(buf)
                else:
                    break

        # get the output from nodejs's stdout and continue till output ends
        def get_output(output_queue):
            while not no_more_output.acquire(False):
                buf = os.read(nodejs.stdout.fileno(), READ_BYTES_SIZE)
                if buf:
                    output_queue.put(buf)

        # get the output from nodejs's stderr and continue till error output ends
        def get_error(error_queue):
            while not no_more_error.acquire(False):
                buf = os.read(nodejs.stderr.fileno(), READ_BYTES_SIZE)
                if buf:
                    error_queue.put(buf)

        # Threads managing nodejs.stdin, nodejs.stdout and nodejs.stderr respectively
        input_thread = threading.Thread(target=put_input, args=(input_queue,))
        input_thread.daemon = True
        input_thread.start()
        output_thread = threading.Thread(target=get_output, args=(output_queue,))
        output_thread.daemon = True
        output_thread.start()
        error_thread = threading.Thread(target=get_error, args=(error_queue,))
        error_thread.daemon = True
        error_thread.start()

        finished = False

        while not finished and timer.is_alive():
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
            except OSError:
                break

    else:
        while not process_finished() and timer.is_alive():
            rready, wready, _ = select.select(rselect, wselect, [])
            try:
                if nodejs.stdin in wready:
                    buf = stdin_buf.read(select.PIPE_BUF)
                    if buf:
                        os.write(nodejs.stdin.fileno(), buf)
                for pipes in ((nodejs.stdout, stdout_buf), (nodejs.stderr, stderr_buf)):
                    if pipes[0] in rready:
                        buf = os.read(pipes[0].fileno(), select.PIPE_BUF)
                        if buf:
                            pipes[1].write(buf)
            except OSError:
                break
    timer.cancel()

    stdin_buf.close()
    stdoutdata = stdout_buf.getvalue()[:-len(PROCESS_FINISHED_STR) - 1]
    stderrdata = stderr_buf.getvalue()[:-len(PROCESS_FINISHED_STR) - 1]

    nodejs.poll()

    if nodejs.poll() not in (None, 0):
        if killed:
            returncode = -1
        else:
            returncode = nodejs.returncode
    else:
        returncode = 0
        # On windows currently a new instance of nodejs process is used due to
        # problem with blocking on read operation on windows
        if onWindows():
            nodejs.kill()

    return returncode, stdoutdata.decode('utf-8'), stderrdata.decode('utf-8')

def code_fragment_to_js(jscript, jslib=""):
    # type: (Text, Text) -> Text
    if isinstance(jscript, six.string_types) \
            and len(jscript) > 1 and jscript[0] == '{':
        inner_js = jscript
    else:
        inner_js = "{return (%s);}" % jscript

    return u"\"use strict\";\n{}\n(function(){})()".format(jslib, inner_js)

def execjs(js,                       # type: Text
           jslib,                    # type: Text
           timeout=None,             # type: float
           force_docker_pull=False,  # type: bool
           debug=False,              # type: bool
           js_console=False          # type: bool
          ):  # type: (...) -> JSON

    fn = code_fragment_to_js(js, jslib)

    returncode, stdout, stderr = exec_js_process(
        fn, timeout=timeout, js_console=js_console,
        force_docker_pull=force_docker_pull)

    if js_console:
        if stderr:
            _logger.info("Javascript console output:")
            _logger.info("----------------------------------------")
            _logger.info('\n'.join(re.findall(
                r'^[[](?:log|err)[]].*$', stderr, flags=re.MULTILINE)))
            _logger.info("----------------------------------------")

    def stdfmt(data):  # type: (Text) -> Text
        if "\n" in data:
            return "\n" + data.strip()
        return data

    def fn_linenum():  # type: () -> Text
        lines = fn.splitlines()
        ofs = 0
        maxlines = 99
        if len(lines) > maxlines:
            ofs = len(lines) - maxlines
            lines = lines[-maxlines:]
        return u"\n".join(u"%02i %s" % (i + ofs + 1, b) for i, b in enumerate(lines))

    if returncode != 0:
        if debug:
            info = u"returncode was: %s\nscript was:\n%s\nstdout was: %s\nstderr was: %s\n" %\
                (returncode, fn_linenum(), stdfmt(stdout), stdfmt(stderr))
        else:
            info = u"Javascript expression was: %s\nstdout was: %s\nstderr was: %s" %\
                (js, stdfmt(stdout), stdfmt(stderr))

        if returncode == -1:
            raise JavascriptException(
                u"Long-running script killed after {} seconds: {}".format(
                    timeout, info))
        else:
            raise JavascriptException(info)

    try:
        return json.loads(stdout)
    except ValueError as err:
        raise JavascriptException(
            u"{}\nscript was:\n{}\nstdout was: '{}'\nstderr was: '{}'\n".format(
                err, fn_linenum(), stdout, stderr))
