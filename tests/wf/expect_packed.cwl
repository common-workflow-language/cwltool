{
    "$graph": [
        {
            "class": "Workflow",
            "doc": "Reverse the lines in a document, then sort those lines.",
            "hints": [
                {
                    "class": "DockerRequirement",
                    "dockerPull": "debian:8"
                }
            ],
            "inputs": [
                {
                    "type": "File",
                    "doc": "The input file to be processed.",
                    "format": "https://www.iana.org/assignments/media-types/text/plain",
                    "default": {
                        "class": "File",
                        "location": "hello.txt"
                    },
                    "id": "#main/input"
                },
                {
                    "type": "boolean",
                    "default": true,
                    "doc": "If true, reverse (decending) sort",
                    "id": "#main/reverse_sort"
                }
            ],
            "outputs": [
                {
                    "type": "File",
                    "outputSource": "#main/sorted/output",
                    "doc": "The output with the lines reversed and sorted.",
                    "id": "#main/output"
                }
            ],
            "steps": [
                {
                    "in": [
                        {
                            "source": "#main/input",
                            "id": "#main/rev/input"
                        }
                    ],
                    "out": [
                        "#main/rev/output"
                    ],
                    "run": "#revtool.cwl",
                    "id": "#main/rev"
                },
                {
                    "in": [
                        {
                            "source": "#main/rev/output",
                            "id": "#main/sorted/input"
                        },
                        {
                            "source": "#main/reverse_sort",
                            "id": "#main/sorted/reverse"
                        }
                    ],
                    "out": [
                        "#main/sorted/output"
                    ],
                    "run": "#sorttool.cwl",
                    "id": "#main/sorted"
                }
            ],
            "id": "#main",
            "$namespaces": {
                "iana": "https://www.iana.org/assignments/media-types/"
            }
        },
        {
            "class": "CommandLineTool",
            "doc": "Reverse each line using the `rev` command",
            "inputs": [
                {
                    "type": "File",
                    "inputBinding": {},
                    "id": "#revtool.cwl/input"
                }
            ],
            "outputs": [
                {
                    "type": "File",
                    "outputBinding": {
                        "glob": "output.txt"
                    },
                    "id": "#revtool.cwl/output"
                }
            ],
            "baseCommand": "rev",
            "stdout": "output.txt",
            "id": "#revtool.cwl"
        },
        {
            "class": "CommandLineTool",
            "doc": "Sort lines using the `sort` command",
            "inputs": [
                {
                    "id": "#sorttool.cwl/reverse",
                    "type": "boolean",
                    "inputBinding": {
                        "position": 1,
                        "prefix": "--reverse"
                    }
                },
                {
                    "id": "#sorttool.cwl/input",
                    "type": "File",
                    "inputBinding": {
                        "position": 2
                    }
                }
            ],
            "outputs": [
                {
                    "id": "#sorttool.cwl/output",
                    "type": "File",
                    "outputBinding": {
                        "glob": "output.txt"
                    }
                }
            ],
            "baseCommand": "sort",
            "stdout": "output.txt",
            "id": "#sorttool.cwl"
        }
    ],
    "cwlVersion": "v1.0",
    "$schemas": [
        "file:///home/mcrusoe/cwltool/tests/wf/empty2.ttl",
        "file:///home/mcrusoe/cwltool/tests/wf/empty.ttl"
    ]
}
