#!/usr/bin/env cwl-runner
{
    "class": "CommandLineTool",
    "cwlVersion": "v1.1.0-dev1",
    "doc": "Print the contents of a file to stdout using 'cat' running in a docker container.",
    "inputs": [
        {
            "id": "file1",
            "type": "File",
            "inputBinding": {"position": 1}
        },
        {
            "id": "numbering",
            "type": ["null", "boolean"],
            "inputBinding": {
                "position": 0,
                "prefix": "-n"
            }
        },
        {
        id: "args.py",
        type: File,
        default: {
          class: File,
          location: args.py
        },
        inputBinding: {
          position: -1
        }
      }
    ],
    "outputs": [],
    "baseCommand": "python",
    "arguments": ["cat"]
}
