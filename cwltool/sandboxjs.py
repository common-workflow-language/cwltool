"""Evaluate CWL Javascript Expressions in a sandbox."""

import errno
import json
import os
import re
import select
import subprocess  # nosec
import threading
from io import BytesIO
from typing import List, Optional, Tuple, cast

from pkg_resources import resource_stream
from schema_salad.utils import json_dumps

from .loghandler import _logger
from .singularity_utils import singularity_supports_userns
from .utils import CWLOutputType, processes_to_kill


class JavascriptException(Exception):
    pass


localdata = threading.local()

default_timeout = 20
have_node_slim = False
# minimum acceptable version of nodejs engine
minimum_node_version_str = "0.10.26"


def check_js_threshold_version(working_alias: str) -> bool:
    """
    Check if the nodeJS engine version on the system with the allowed minimum version.

    https://github.com/nodejs/node/blob/master/CHANGELOG.md#nodejs-changelog
    """
    # parse nodejs version into int Tuple: 'v4.2.6\n' -> [4, 2, 6]
    current_version_str = subprocess.check_output(  # nosec
        [working_alias, "-v"], universal_newlines=True
    )

    current_version = [
        int(v) for v in current_version_str.strip().strip("v").split(".")
    ]
    minimum_node_version = [int(v) for v in minimum_node_version_str.split(".")]

    return current_version >= minimum_node_version


def new_js_proc(
    js_text: str, force_docker_pull: bool = False, container_engine: str = "docker"
) -> "subprocess.Popen[str]":
    """Return a subprocess ready to submit javascript to."""
    required_node_version, docker = (False,) * 2
    nodejs = None  # type: Optional[subprocess.Popen[str]]
    trynodes = ("nodejs", "node")
    for n in trynodes:
        try:
            if (
                subprocess.check_output(  # nosec
                    [n, "--eval", "process.stdout.write('t')"], universal_newlines=True
                )
                != "t"
            ):
                continue
            else:
                nodejs = subprocess.Popen(  # nosec
                    [n, "--eval", js_text],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                processes_to_kill.append(nodejs)
                required_node_version = check_js_threshold_version(n)
                break
        except (subprocess.CalledProcessError, OSError):
            pass

    if nodejs is None or nodejs is not None and required_node_version is False:
        try:
            nodeimg = "docker.io/node:slim"
            global have_node_slim
            if container_engine == "singularity":
                nodeimg = f"docker://{nodeimg}"

            if not have_node_slim:
                if container_engine in ("docker", "podman"):
                    dockerimgs = subprocess.check_output(  # nosec
                        [container_engine, "images", "-q", nodeimg],
                        universal_newlines=True,
                    )
                elif container_engine != "singularity":
                    raise Exception(f"Unknown container_engine: {container_engine}.")
                # if output is an empty string
                if (
                    container_engine == "singularity"
                    or len(dockerimgs.split("\n")) <= 1
                    or force_docker_pull
                ):
                    # pull node:slim docker container
                    nodejs_pull_commands = [container_engine, "pull"]
                    if container_engine == "singularity":
                        nodejs_pull_commands.append("--force")
                    nodejs_pull_commands.append(nodeimg)
                    nodejsimg = subprocess.check_output(  # nosec
                        nodejs_pull_commands, universal_newlines=True
                    )
                    _logger.debug(
                        "Pulled Docker image %s %s using %s",
                        nodeimg,
                        nodejsimg,
                        container_engine,
                    )
                have_node_slim = True
            nodejs_commands = [
                container_engine,
            ]
            if container_engine != "singularity":
                nodejs_commands.extend(
                    [
                        "run",
                        "--attach=STDIN",
                        "--attach=STDOUT",
                        "--attach=STDERR",
                        "--sig-proxy=true",
                        "--interactive",
                        "--rm",
                    ]
                )
            else:
                nodejs_commands.extend(
                    [
                        "exec",
                        "--contain",
                        "--ipc",
                        "--cleanenv",
                        "--userns" if singularity_supports_userns() else "--pid",
                    ]
                )
            nodejs_commands.extend(
                [
                    nodeimg,
                    "node",
                    "--eval",
                    js_text,
                ],
            )
            _logger.debug("Running nodejs via %s", nodejs_commands[:-1])
            nodejs = subprocess.Popen(  # nosec
                nodejs_commands,
                universal_newlines=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
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
            "cwltool requires Node.js engine to evaluate and validate "
            "Javascript expressions, but couldn't find it.  Tried {}, "
            f"{container_engine} run node:slim".format(", ".join(trynodes))
        )

    # docker failed, but nodejs is installed on system but the version is below the required version
    if docker is False and required_node_version is False:
        raise JavascriptException(
            "cwltool requires minimum v{} version of Node.js engine.".format(
                minimum_node_version_str
            ),
            "Try updating: https://docs.npmjs.com/getting-started/installing-node",
        )

    return nodejs


PROCESS_FINISHED_STR = "r1cepzbhUTxtykz5XTC4\n"


def exec_js_process(
    js_text: str,
    timeout: float = default_timeout,
    js_console: bool = False,
    context: Optional[str] = None,
    force_docker_pull: bool = False,
    container_engine: str = "docker",
) -> Tuple[int, str, str]:

    if not hasattr(localdata, "procs"):
        localdata.procs = {}

    if js_console and context is not None:
        raise NotImplementedError("js_console=True and context not implemented")

    if js_console:
        js_engine = "cwlNodeEngineJSConsole.js"
        _logger.warning(
            "Running with support for javascript console in expressions (DO NOT USE IN PRODUCTION)"
        )
    elif context is not None:
        js_engine = "cwlNodeEngineWithContext.js"
    else:
        js_engine = "cwlNodeEngine.js"

    created_new_process = False

    if context is not None:
        nodejs = localdata.procs.get((js_engine, context))
    else:
        nodejs = localdata.procs.get(js_engine)

    if nodejs is None or nodejs.poll() is not None:
        res = resource_stream(__name__, js_engine)
        js_engine_code = res.read().decode("utf-8")

        created_new_process = True

        new_proc = new_js_proc(
            js_engine_code,
            force_docker_pull=force_docker_pull,
            container_engine=container_engine,
        )

        if context is None:
            localdata.procs[js_engine] = new_proc
            nodejs = new_proc
        else:
            localdata.procs[(js_engine, context)] = new_proc
            nodejs = new_proc

    killed = []

    def terminate() -> None:
        """Kill the node process if it exceeds timeout limit."""
        try:
            killed.append(True)
            nodejs.kill()
        except OSError:
            pass

    timer = threading.Timer(timeout, terminate)
    timer.daemon = True
    timer.start()

    stdin_text = ""
    if created_new_process and context is not None:
        stdin_text = json_dumps(context) + "\n"
    stdin_text += json_dumps(js_text) + "\n"

    stdin_buf = BytesIO(stdin_text.encode("utf-8"))
    stdout_buf = BytesIO()
    stderr_buf = BytesIO()

    rselect = [nodejs.stdout, nodejs.stderr]  # type: List[BytesIO]
    wselect = [nodejs.stdin]  # type: List[BytesIO]

    def process_finished() -> bool:
        return stdout_buf.getvalue().decode("utf-8").endswith(
            PROCESS_FINISHED_STR
        ) and stderr_buf.getvalue().decode("utf-8").endswith(PROCESS_FINISHED_STR)

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
    stdoutdata = stdout_buf.getvalue()[: -len(PROCESS_FINISHED_STR) - 1]
    stderrdata = stderr_buf.getvalue()[: -len(PROCESS_FINISHED_STR) - 1]

    nodejs.poll()

    if nodejs.poll() not in (None, 0):
        if killed:
            returncode = -1
        else:
            returncode = nodejs.returncode
    else:
        returncode = 0

    return returncode, stdoutdata.decode("utf-8"), stderrdata.decode("utf-8")


def code_fragment_to_js(jscript: str, jslib: str = "") -> str:
    if isinstance(jscript, str) and len(jscript) > 1 and jscript[0] == "{":
        inner_js = jscript
    else:
        inner_js = "{return (%s);}" % jscript

    return f'"use strict";\n{jslib}\n(function(){inner_js})()'


def execjs(
    js: str,
    jslib: str,
    timeout: float,
    force_docker_pull: bool = False,
    debug: bool = False,
    js_console: bool = False,
    container_engine: str = "docker",
) -> CWLOutputType:

    fn = code_fragment_to_js(js, jslib)

    returncode, stdout, stderr = exec_js_process(
        fn,
        timeout,
        js_console=js_console,
        force_docker_pull=force_docker_pull,
        container_engine=container_engine,
    )

    if js_console:
        if stderr is not None:
            _logger.info("Javascript console output:")
            _logger.info("----------------------------------------")
            _logger.info(
                "\n".join(
                    re.findall(r"^[[](?:log|err)[]].*$", stderr, flags=re.MULTILINE)
                )
            )
            _logger.info("----------------------------------------")

    def stdfmt(data: str) -> str:
        if "\n" in data:
            return "\n" + data.strip()
        return data

    def fn_linenum() -> str:
        lines = fn.splitlines()
        ofs = 0
        maxlines = 99
        if len(lines) > maxlines:
            ofs = len(lines) - maxlines
            lines = lines[-maxlines:]
        return "\n".join("%02i %s" % (i + ofs + 1, b) for i, b in enumerate(lines))

    if returncode != 0:
        if debug:
            info = (
                "returncode was: %s\nscript was:\n%s\nstdout was: %s\nstderr was: %s\n"
                % (returncode, fn_linenum(), stdfmt(stdout), stdfmt(stderr))
            )
        else:
            info = (
                "Javascript expression was: {}\nstdout was: {}\nstderr was: {}".format(
                    js,
                    stdfmt(stdout),
                    stdfmt(stderr),
                )
            )

        if returncode == -1:
            raise JavascriptException(
                f"Long-running script killed after {timeout} seconds: {info}"
            )
        else:
            raise JavascriptException(info)

    try:
        return cast(CWLOutputType, json.loads(stdout))
    except ValueError as err:
        raise JavascriptException(
            "{}\nscript was:\n{}\nstdout was: '{}'\nstderr was: '{}'\n".format(
                err, fn_linenum(), stdout, stderr
            )
        ) from err
