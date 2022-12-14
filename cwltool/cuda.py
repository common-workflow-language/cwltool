import subprocess  # nosec
import xml.dom.minidom  # nosec
from typing import Tuple

from .loghandler import _logger
from .utils import CWLObjectType


def cuda_version_and_device_count() -> Tuple[str, int]:
    try:
        out = subprocess.check_output(["nvidia-smi", "-q", "-x"])  # nosec
    except Exception as e:
        _logger.warning("Error checking CUDA version with nvidia-smi: %s", e)
        return ("", 0)
    dm = xml.dom.minidom.parseString(out)  # nosec
    ag = dm.getElementsByTagName("attached_gpus")[0].firstChild
    cv = dm.getElementsByTagName("cuda_version")[0].firstChild
    return (cv.data, int(ag.data))


def cuda_check(cuda_req: CWLObjectType, requestCount: int) -> int:
    try:
        vmin = float(str(cuda_req["cudaVersionMin"]))
        version, devices = cuda_version_and_device_count()
        if version == "":
            # nvidia-smi not detected, or failed some other way
            return 0
        versionf = float(version)
        if versionf < vmin:
            _logger.warning(
                "CUDA version '%s' is less than minimum version '%s'", version, vmin
            )
            return 0
        if requestCount > devices:
            _logger.warning(
                "Requested %d GPU devices but only %d available", requestCount, devices
            )
            return 0
        return requestCount
    except Exception as e:
        _logger.warning("Error checking CUDA requirements: %s", e)
        return 0
