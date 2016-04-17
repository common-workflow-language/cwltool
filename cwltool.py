#!/usr/bin/env python
"""Convienance entry point for cwltool."""

import sys
from cwltool import main

if __name__ == "__main__":
    sys.exit(main.main(sys.argv[1:]))
