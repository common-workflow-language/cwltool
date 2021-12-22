import subprocess
import xml.dom.minidom
from .loghandler import _logger
from .utils import CWLObjectType

from typing import Tuple, cast


def cuda_version_and_device_count() -> Tuple[str, int]:
    try:
        res = subprocess.run(["nvidia-smi", "-q", "-x"], capture_output=True)
    except Exception as e:
        _logger.warning(e)
        return ("", 0)
    out = res.stdout
    dm = xml.dom.minidom.parseString(out)
    ag = dm.getElementsByTagName("attached_gpus")[0].firstChild
    cv = dm.getElementsByTagName("cuda_version")[0].firstChild
    return (cv.data, int(ag.data))


def cuda_check(cuda_req: CWLObjectType) -> int:
    try:
        vmin = float(str(cuda_req["cudaVersionMin"]))
        version, devices = cuda_version_and_device_count()
        versionf = float(version)
        if versionf < vmin:
            _logger.warning(
                "CUDA version '%s' is less than minimum version '%s'", version, vmin
            )
            return 0
        dmin = cast(int, cuda_req.get("deviceCountMin", 1))
        dmax = cast(int, cuda_req.get("deviceCountMax", dmin))
        if devices < dmin:
            _logger.warning(
                "Requested at least %d GPU devices but only %d available", dmin, devices
            )
            return 0
        return min(dmax, devices)
    except Exception as e:
        _logger.warning("Error checking CUDA requirements: %s", e)
        return 0
