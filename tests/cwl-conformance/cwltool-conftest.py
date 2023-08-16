"""
Example configuration for pytest + cwltest plugin using cwltool directly.

Calls cwltool via Python, instead of a subprocess via `--cwl-runner cwltool`.
"""
import json
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

from cwltest import utils


def pytest_cwl_execute_test(
    config: utils.CWLTestConfig, processfile: str, jobfile: Optional[str]
) -> Tuple[int, Optional[Dict[str, Any]]]:
    """Use the CWL reference runner (cwltool) to execute tests."""
    from cwltool import main
    from cwltool.errors import WorkflowException

    stdout = StringIO()
    argsl: List[str] = [f"--outdir={config.outdir}"]
    if config.runner_quiet:
        argsl.append("--quiet")
    elif config.verbose:
        argsl.append("--debug")
    argsl.extend(config.args)
    argsl.append(processfile)
    if jobfile:
        argsl.append(jobfile)
    try:
        result = main.main(argsl=argsl, stdout=stdout)
    except WorkflowException:
        return 1, {}
    out = stdout.getvalue()
    return result, json.loads(out) if out else {}
