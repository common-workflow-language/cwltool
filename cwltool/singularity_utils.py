"""Support for executing Docker containers using the Singularity 2.x engine."""

import os
import os.path
from subprocess import DEVNULL, PIPE, Popen, TimeoutExpired  # nosec
from typing import Optional

_USERNS = None  # type: Optional[bool]


def singularity_supports_userns() -> bool:
    """Confirm if the version of Singularity install supports the --userns flag."""
    global _USERNS  # pylint: disable=global-statement
    if _USERNS is None:
        try:
            hello_image = os.path.join(os.path.dirname(__file__), "hello.simg")
            result = Popen(  # nosec
                ["singularity", "exec", "--userns", hello_image, "true"],
                stderr=PIPE,
                stdout=DEVNULL,
                universal_newlines=True,
            ).communicate(timeout=60)[1]
            _USERNS = (
                "No valid /bin/sh" in result
                or "/bin/sh doesn't exist in container" in result
                or "executable file not found in" in result
            )
        except TimeoutExpired:
            _USERNS = False
    return _USERNS
