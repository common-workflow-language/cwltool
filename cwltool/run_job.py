"""Only used when there is a job script or CWLTOOL_FORCE_SHELL_POPEN=1."""
import json
import os
import subprocess  # nosec
import sys
from typing import BinaryIO, Dict, List, Optional, TextIO, Union


def handle_software_environment(cwl_env: Dict[str, str], script: str) -> Dict[str, str]:
    """Update the provided environment dict by running the script."""
    exec_env = cwl_env.copy()
    exec_env["_CWLTOOL"] = "1"
    res = subprocess.run(["bash", script], shell=False, env=exec_env)  # nosec
    if res.returncode != 0:
        sys.stderr.write(
            "Error while using SoftwareRequirements to modify environment\n"
        )
        return cwl_env

    env = cwl_env.copy()
    with open("output_environment.dat") as _:
        data = _.read().strip("\0")
    for line in data.split("\0"):
        key, val = line.split("=", 1)
        if key in ("_", "PWD", "SHLVL", "TMPDIR", "HOME", "_CWLTOOL"):
            # Skip some variables that are meaningful to the shell or set
            # specifically by the CWL runtime environment.
            continue
        env[key] = val
    return env


def main(argv: List[str]) -> int:
    """
    Read in the configuration JSON and execute the commands.

    The first argument is the path to the JSON dictionary file containing keys:
      "commands": an array of strings that represents the command line to run
      "cwd": A string specifying which directory to run in
      "env": a dictionary of strings containing the environment variables to set
      "stdin_path": a string (or a null) giving the path that should be piped to STDIN
      "stdout_path": a string (or a null) giving the path that should receive the STDOUT
      "stderr_path": a string (or a null) giving the path that should receive the STDERR

    The second argument is optional, it specifies a shell script to execute prior,
      and the environment variables it sets will be combined with the environment
      variables from the "env" key in the JSON dictionary from the first argument.
    """
    with open(argv[1]) as f:
        popen_description = json.load(f)
        commands = popen_description["commands"]
        cwd = popen_description["cwd"]
        env = popen_description["env"]
        env["PATH"] = os.environ.get("PATH")
        stdin_path = popen_description["stdin_path"]
        stdout_path = popen_description["stdout_path"]
        stderr_path = popen_description["stderr_path"]
        if stdin_path is not None:
            stdin: Union[BinaryIO, int] = open(stdin_path, "rb")
        else:
            stdin = subprocess.PIPE
        if stdout_path is not None:
            stdout: Union[BinaryIO, TextIO] = open(stdout_path, "wb")
        else:
            stdout = sys.stderr
        if stderr_path is not None:
            stderr: Union[BinaryIO, TextIO] = open(stderr_path, "wb")
        else:
            stderr = sys.stderr

        try:
            env_script: Optional[str] = argv[2]
        except IndexError:
            env_script = None
        if env_script is not None:
            env = handle_software_environment(env, env_script)

        sp = subprocess.Popen(  # nosec
            commands,
            shell=False,
            close_fds=True,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=env,
            cwd=cwd,
        )
        if sp.stdin:
            sp.stdin.close()
        rcode = sp.wait()
        if not isinstance(stdin, int):
            stdin.close()
        if stdout is not sys.stderr:
            stdout.close()
        if stderr is not sys.stderr:
            stderr.close()
    return rcode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
