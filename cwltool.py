#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""Convenience entry point for cwltool.

This can be used instead of the recommended method of `./setup.py install`
or `./setup.py develop` and then using the generated `cwltool` executable.
"""

import sys

from cwltool import main

if __name__ == "__main__":
    main.run(sys.argv[1:])
