{
    "cwlVersion": "v1.0",
    "$schemas": ["file:///home/peter/work/cwltool/tests/wf/empty.ttl"],
    "$graph": [
        {
            "inputs": [
                {
                    "doc": "The input file to be processed.",
                    "type": "File",
                    "id": "#main/input",
                    "default": {
                      "class": "File",
                      "location": "hello.txt"
                    }
                },
                {
                    "default": true,
                    "doc": "If true, reverse (decending) sort",
                    "type": "boolean",
                    "id": "#main/reverse_sort"
                }
            ],
            "doc": "Reverse the lines in a document, then sort those lines.",
            "class": "Workflow",
            "steps": [
                {
                    "out": [
                        "#main/rev/output"
                    ],
                    "run": "#revtool.cwl",
                    "id": "#main/rev",
                    "in": [
                        {
                            "source": "#main/input",
                            "id": "#main/rev/input"
                        }
                    ]
                },
                {
                    "out": [
                        "#main/sorted/output"
                    ],
                    "run": "#sorttool.cwl",
                    "id": "#main/sorted",
                    "in": [
                        {
                            "source": "#main/rev/output",
                            "id": "#main/sorted/input"
                        },
                        {
                            "source": "#main/reverse_sort",
                            "id": "#main/sorted/reverse"
                        }
                    ]
                }
            ],
            "outputs": [
                {
                    "outputSource": "#main/sorted/output",
                    "type": "File",
                    "id": "#main/output",
                    "doc": "The output with the lines reversed and sorted."
                }
            ],
            "id": "#main",
            "hints": [
                {
                    "dockerPull": "debian:8",
                    "class": "DockerRequirement"
                }
            ]
        },
        {
            "inputs": [
                {
                    "inputBinding": {},
                    "type": "File",
                    "id": "#revtool.cwl/input"
                }
            ],
            "stdout": "output.txt",
            "doc": "Reverse each line using the `rev` command",
            "baseCommand": "rev",
            "class": "CommandLineTool",
            "outputs": [
                {
                    "outputBinding": {
                        "glob": "output.txt"
                    },
                    "type": "File",
                    "id": "#revtool.cwl/output"
                }
            ],
            "id": "#revtool.cwl"
        },
        {
            "inputs": [
                {
                    "inputBinding": {
                        "position": 1,
                        "prefix": "--reverse"
                    },
                    "type": "boolean",
                    "id": "#sorttool.cwl/reverse"
                },
                {
                    "inputBinding": {
                        "position": 2
                    },
                    "type": "File",
                    "id": "#sorttool.cwl/input"
                }
            ],
            "stdout": "output.txt",
            "doc": "Sort lines using the `sort` command",
            "baseCommand": "sort",
            "class": "CommandLineTool",
            "outputs": [
                {
                    "outputBinding": {
                        "glob": "output.txt"
                    },
                    "type": "File",
                    "id": "#sorttool.cwl/output"
                }
            ],
            "id": "#sorttool.cwl"
        }
    ]
}
