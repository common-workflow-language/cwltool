#!/usr/bin/env python3
import sys
import json

content = ""
cmd = {
    "cwlVersion": "v1.1",
    "class": "CommandLineTool",
    "requirements": {
        "InitialWorkDirRequirement": {
            "listing": [{
                "entry": "",
                "entryname": "script.sh"
            }]
        }
    },
    "inputs": {},
    "outputs": {},
    "arguments": ["sh", "script.sh"]
}

f = open(sys.argv[1], "rt")
for ln in f:
    ln = ln.rstrip()
    if ln.startswith("##input"):
        sp = ln.split(" ")
        cmd["inputs"][sp[1]] = sp[2]
        if sp[2] in ("File", "Directory"):
            path=".path"
        else:
            path=""
        content += "{var}='$(inputs.{var}{path})'\n".format(var=sp[1], path=path)
    elif ln.startswith("##output"):
        sp = ln.split(" ")
        cmd["outputs"][sp[1]] = {
            "type": "File",
            "outputBinding": {
                "glob": sp[2]
            }
        }
    else:
        content += ln+"\n"

cmd["requirements"]["InitialWorkDirRequirement"]["listing"][0]["entry"] = content

print(json.dumps(cmd, indent=4))
