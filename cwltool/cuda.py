"""Support utilities for CUDA."""

import subprocess  # nosec
import xml.dom.minidom  # nosec
from typing import Tuple

from .loghandler import _logger
from .utils import CWLObjectType


def cuda_device_count() -> str:
    """Determine the number of attached CUDA GPUs."""
    # For the number of GPUs, we can use the following query
    cmd = ["nvidia-smi", "--query-gpu=count", "--format=csv,noheader"]
    try:
        # This is equivalent to subprocess.check_output, but use
        # subprocess.run so we can use separate MagicMocks in test_cuda.py
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)  # nosec
    except Exception as e:
        _logger.warning("Error checking number of GPUs with nvidia-smi: %s", e)
        return "0"
    # NOTE: On a machine with N GPUs the query return N lines, each containing N.
    return proc.stdout.decode("utf-8").split("\n")[0]


def cuda_version_and_device_count() -> Tuple[str, int]:
    """Determine the CUDA version and number of attached CUDA GPUs."""
    count = int(cuda_device_count())

    # Since there is no specific query for the cuda version, we have to use
    # `nvidia-smi -q -x`
    # However, apparently nvidia-smi is not safe to call concurrently.
    # With --parallel, sometimes the returned XML will contain
    # <process_name>\xff...\xff</process_name>
    # (or other arbitrary bytes) and xml.dom.minidom.parseString will raise
    # "xml.parsers.expat.ExpatError: not well-formed (invalid token)"
    # So we either need to use `grep -v process_name` to blacklist that tag,
    # (and hope that no other tags cause problems in the future)
    # or better yet use `grep cuda_version` to only grab the tags we will use.
    cmd = "nvidia-smi -q -x | grep cuda_version"
    try:
        out = subprocess.check_output(cmd, shell=True)  # nosec
    except Exception as e:
        _logger.warning("Error checking CUDA version with nvidia-smi: %s", e)
        return ("", 0)

    try:
        dm = xml.dom.minidom.parseString(out)  # nosec
    except xml.parsers.expat.ExpatError as e:
        _logger.warning("Error parsing XML stdout of nvidia-smi: %s", e)
        _logger.warning("stdout: %s", out)
        return ("", 0)

    cv = dm.getElementsByTagName("cuda_version")
    if len(cv) < 1 or cv[0].firstChild is None:
        _logger.warning(
            "Error checking CUDA version with nvidia-smi. Missing 'cuda_version' or it is empty.: %s",
            out,
        )
        return ("", 0)
    cv_element = cv[0].firstChild

    if isinstance(cv_element, xml.dom.minidom.Text):
        return (cv_element.data, count)
    _logger.warning(
        "Error checking CUDA version with nvidia-smi. 'cuda_version' was not a text node: %s",
        out,
    )
    return ("", 0)


def cuda_check(cuda_req: CWLObjectType, requestCount: int) -> int:
    try:
        vmin = float(str(cuda_req["cudaVersionMin"]))
        version, devices = cuda_version_and_device_count()
        if version == "":
            # nvidia-smi not detected, or failed some other way
            return 0
        versionf = float(version)
        if versionf < vmin:
            _logger.warning("CUDA version '%s' is less than minimum version '%s'", version, vmin)
            return 0
        if requestCount > devices:
            _logger.warning("Requested %d GPU devices but only %d available", requestCount, devices)
            return 0
        return requestCount
    except Exception as e:
        _logger.warning("Error checking CUDA requirements: %s", e)
        return 0
