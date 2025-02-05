"""Support for executing Docker format containers using Singularity {2,3}.x or Apptainer 1.x."""

import os
import os.path
import subprocess  # nosec
from typing import Optional

_USERNS: Optional[bool] = None


def singularity_supports_userns() -> bool:
    """Confirm if the version of Singularity install supports the --userns flag."""
    global _USERNS  # pylint: disable=global-statement
    if _USERNS is None:
        try:
            hello_image = os.path.join(os.path.dirname(__file__), "hello.simg")
            result = subprocess.run(  # nosec
                ["singularity", "exec", "--userns", hello_image, "true"],
                capture_output=True,
                timeout=60,
                text=True,
            ).stderr
            _USERNS = (
                "No valid /bin/sh" in result
                or "/bin/sh doesn't exist in container" in result
                or "executable file not found in" in result
            )
        except subprocess.TimeoutExpired:
            _USERNS = False
    return _USERNS
