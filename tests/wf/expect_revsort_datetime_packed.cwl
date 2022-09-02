{
    "class": "Workflow",
    "doc": "Reverse the lines in a document, then sort those lines.",
    "cwlVersion": "v1.0",
    "hints": [
        {
            "class": "DockerRequirement",
            "dockerPull": "docker.io/debian:stable-slim"
        }
    ],
    "inputs": [
        {
            "type": "File",
            "doc": "The input file to be processed.",
            "format": "iana:text/plain",
            "default": {
                "class": "File",
                "location": "hello.txt"
            },
            "id": "workflow_input"
        },
        {
            "type": "boolean",
            "default": true,
            "doc": "If true, reverse (descending) sort",
            "id": "reverse_sort"
        }
    ],
    "outputs": [
        {
            "type": "File",
            "outputSource": "sorted/sorted_output",
            "doc": "The output with the lines reversed and sorted.",
            "id": "sorted_output"
        }
    ],
    "steps": [
        {
            "in": [
                {
                    "source": "workflow_input",
                    "id": "revtool_input"
                }
            ],
            "out": [
                "revtool_output"
            ],
            "run": {
                "class": "CommandLineTool",
                "cwlVersion": "v1.0",
                "doc": "Reverse each line using the `rev` command",
                "$schemas": [
                    "empty.ttl"
                ],
                "inputs": [
                    {
                        "type": "File",
                        "inputBinding": {},
                        "id": "revtool_input"
                    }
                ],
                "outputs": [
                    {
                        "type": "File",
                        "outputBinding": {
                            "glob": "output.txt"
                        },
                        "id": "revtool_output"
                    }
                ],
                "baseCommand": "rev",
                "stdout": "output.txt",
                "requirements": []
            },
            "id": "rev"
        },
        {
            "in": [
                {
                    "source": "rev/revtool_output",
                    "id": "sorted_input"
                },
                {
                    "source": "reverse_sort",
                    "id": "reverse"
                }
            ],
            "out": [
                "sorted_output"
            ],
            "run": {
                "class": "CommandLineTool",
                "doc": "Sort lines using the `sort` command",
                "cwlVersion": "v1.0",
                "inputs": [
                    {
                        "id": "reverse",
                        "type": "boolean",
                        "inputBinding": {
                            "position": 1,
                            "prefix": "--reverse"
                        }
                    },
                    {
                        "id": "sorted_input",
                        "type": "File",
                        "inputBinding": {
                            "position": 2
                        }
                    }
                ],
                "outputs": [
                    {
                        "id": "sorted_output",
                        "type": "File",
                        "outputBinding": {
                            "glob": "output.txt"
                        }
                    }
                ],
                "baseCommand": "sort",
                "stdout": "output.txt",
                "requirements": []
            },
            "id": "sorted"
        }
    ],
    "$namespaces": {
        "iana": "https://www.iana.org/assignments/media-types/",
        "s": "http://schema.org/"
    },
    "$schemas": [
        "https://schema.org/version/latest/schemaorg-current-https.rdf",
        "empty2.ttl"
    ],
    "s:dateCreated": "2020-10-08",
    "requirements": []
}
