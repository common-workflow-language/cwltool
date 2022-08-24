{
    "$graph": [
        {
            "class": "CommandLineTool",
            "doc": "Reverse each line using the `rev` command",
            "inputs": [
                {
                    "type": "File",
                    "inputBinding": {},
                    "id": "#revtool.cwl/revtool_input"
                }
            ],
            "outputs": [
                {
                    "type": "File",
                    "outputBinding": {
                        "glob": "output.txt"
                    },
                    "id": "#revtool.cwl/revtool_output"
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
                    "id": "#sorttool.cwl/sorted_input",
                    "type": "File",
                    "inputBinding": {
                        "position": 2
                    }
                }
            ],
            "outputs": [
                {
                    "id": "#sorttool.cwl/sorted_output",
                    "type": "File",
                    "outputBinding": {
                        "glob": "output.txt"
                    }
                }
            ],
            "baseCommand": "sort",
            "stdout": "output.txt",
            "id": "#sorttool.cwl"
        },
        {
            "class": "Workflow",
            "doc": "Reverse the lines in a document, then sort those lines.",
            "hints": [
                {
                    "class": "DockerRequirement",
                    "dockerPull": "docker.io/debian:stable-slim"
                }
            ],
            "inputs": [
                {
                    "type": "string",
                    "doc": "Here to test for a bug in --pack",
                    "id": "#main/name"
                },
                {
                    "type": "boolean",
                    "default": true,
                    "doc": "If true, reverse (descending) sort",
                    "id": "#main/reverse_sort"
                },
                {
                    "type": "File",
                    "doc": "The input file to be processed.",
                    "format": "https://www.iana.org/assignments/media-types/text/plain",
                    "default": {
                        "class": "File",
                        "location": "hello.txt"
                    },
                    "id": "#main/workflow_input"
                }
            ],
            "outputs": [
                {
                    "type": "File",
                    "outputSource": "#main/sorted/sorted_output",
                    "doc": "The output with the lines reversed and sorted.",
                    "id": "#main/sorted_output"
                }
            ],
            "steps": [
                {
                    "in": [
                        {
                            "source": "#main/workflow_input",
                            "id": "#main/rev/revtool_input"
                        }
                    ],
                    "out": [
                        "#main/rev/revtool_output"
                    ],
                    "run": "#revtool.cwl",
                    "id": "#main/rev"
                },
                {
                    "in": [
                        {
                            "source": "#main/reverse_sort",
                            "id": "#main/sorted/reverse"
                        },
                        {
                            "source": "#main/rev/revtool_output",
                            "id": "#main/sorted/sorted_input"
                        }
                    ],
                    "out": [
                        "#main/sorted/sorted_output"
                    ],
                    "run": "#sorttool.cwl",
                    "id": "#main/sorted"
                }
            ],
            "id": "#main"
        }
    ],
    "cwlVersion": "v1.0",
    "$schemas": [
        "empty2.ttl",
        "empty.ttl"
    ],
    "$namespaces": {
        "iana": "https://www.iana.org/assignments/media-types/"
    }
}
