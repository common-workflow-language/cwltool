r"""Python script that acts like (GNU coreutils) env -0.

When run as a script, it prints the the environment as
`(VARNAME=value\0)*`.

Ideally we would just use `env -0`, because python (thanks to PEPs 538
and 540) will set zero to two environment variables to better handle
Unicode-locale interactions, however BSD familiy implementations of
`env` do not all support the `-0` flag so we supply this script that
produces equivalent output.
"""

import os
from typing import Dict


def deserialize_env(data: str) -> Dict[str, str]:
    """Deserialize the output of `env -0` to dictionary."""
    ans = {}
    for item in data.strip("\0").split("\0"):
        key, val = item.split("=", 1)
        ans[key] = val
    return ans


def main() -> None:
    """Print the null-separated enviroment to stdout."""
    for k, v in os.environ.items():
        print(f"{k}={v}", end="\0")


if __name__ == "__main__":
    main()
