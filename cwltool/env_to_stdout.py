r"""Python script that acts like (GNU coreutils) env -0.

When run as a script, it prints the the environment as
`(VARNAME=value\0)*`.

Ideally we would just use `env -0`, because python (thanks to PEPs 538
and 540) will set zero to two environment variables to better handle
Unicode-locale interactions, however BSD family implementations of
`env` do not all support the `-0` flag so we supply this script that
produces equivalent output.
"""

import os
from typing import Dict


def deserialize_env(data: str) -> Dict[str, str]:
    """Deserialize the output of `env -0` to dictionary."""
    result = {}
    for item in data.strip("\0").split("\0"):
        key, val = item.split("=", 1)
        result[key] = val
    return result


def main() -> None:
    """Print the null-separated environment to stdout."""
    for k, v in os.environ.items():
        print(f"{k}={v}", end="\0")


if __name__ == "__main__":
    main()
