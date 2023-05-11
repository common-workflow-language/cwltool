"""Support utilities for CUDA."""

import subprocess  # nosec
import xml.dom.minidom  # nosec
from typing import Tuple

from .loghandler import _logger
from .utils import CWLObjectType


def cuda_version_and_device_count() -> Tuple[str, int]:
    """Determine the CUDA version and number of attached CUDA GPUs."""
    try:
        out = subprocess.check_output(["nvidia-smi", "-q", "-x"])  # nosec
    except Exception as e:
        _logger.warning("Error checking CUDA version with nvidia-smi: %s", e)
        return ("", 0)
    dm = xml.dom.minidom.parseString(out)  # nosec

    ag = dm.getElementsByTagName("attached_gpus")
    if len(ag) < 1 or ag[0].firstChild is None:
        _logger.warning(
            "Error checking CUDA version with nvidia-smi. Missing 'attached_gpus' or it is empty.: %s",
            out,
        )
        return ("", 0)
    ag_element = ag[0].firstChild

    cv = dm.getElementsByTagName("cuda_version")
    if len(cv) < 1 or cv[0].firstChild is None:
        _logger.warning(
            "Error checking CUDA version with nvidia-smi. Missing 'cuda_version' or it is empty.: %s",
            out,
        )
        return ("", 0)
    cv_element = cv[0].firstChild

    if isinstance(cv_element, xml.dom.minidom.Text) and isinstance(
        ag_element, xml.dom.minidom.Text
    ):
        return (cv_element.data, int(ag_element.data))
    _logger.warning(
        "Error checking CUDA version with nvidia-smi. "
        "Either 'attached_gpus' or 'cuda_version' was not a text node: %s",
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
