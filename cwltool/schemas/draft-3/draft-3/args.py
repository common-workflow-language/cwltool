#!/usr/bin/env python
import json
import os
import sys

args = [os.path.basename(a) for a in sys.argv[1:]]
with open("cwl.output.json", "w") as f:
    json.dump({"args": args}, f)
