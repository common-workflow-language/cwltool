{
    "class": "Workflow",
    "cwlVersion": "v1.2",
    "id": "abstract_cosifer_workflow",
    "label": "abstract-cosifer-workflow",
    "inputs": [
        {
            "type": "File",
            "doc": "Gene expression data matrix",
            "id": "data_matrix"
        },
        {
            "type": [
                "null",
                "File"
            ],
            "doc": "Optional GMT file to perform inference on multiple gene sets",
            "id": "gmt_filepath"
        },
        {
            "type": [
                "null",
                "int"
            ],
            "doc": "Column index in the data. Defaults to None, a.k.a., no index",
            "id": "index_col"
        },
        {
            "type": "string",
            "doc": "Path to the output directory",
            "id": "outdir"
        },
        {
            "type": [
                "null",
                "string"
            ],
            "doc": "Separator for the data. Defaults to .",
            "id": "separator"
        },
        {
            "type": [
                "null",
                "boolean"
            ],
            "doc": "Flag that indicates that data contain the samples on rows. Defaults to False.",
            "id": "samples_on_rows"
        }
    ],
    "outputs": [
        {
            "type": "Directory",
            "outputSource": "abstract_cosifer/resdir",
            "id": "resdir"
        }
    ],
    "steps": [
        {
            "run": {
                "class": "Operation",
                "cwlVersion": "v1.2",
                "requirements": [
                    {
                        "dockerPull": "docker.io/tsenit/cosifer:b4d5af45d2fc54b6bff2a9153a8e9054e560302e",
                        "class": "DockerRequirement"
                    }
                ],
                "inputs": [
                    {
                        "type": "File",
                        "id": "data_matrix"
                    },
                    {
                        "type": [
                            "null",
                            "string"
                        ],
                        "doc": "The separator used in the data_matrix file",
                        "id": "separator"
                    },
                    {
                        "type": [
                            "null",
                            "int"
                        ],
                        "id": "index_col"
                    },
                    {
                        "type": [
                            "null",
                            "File"
                        ],
                        "id": "gmt_filepath"
                    },
                    {
                        "type": [
                            "null",
                            "string"
                        ],
                        "id": "outdir"
                    },
                    {
                        "type": [
                            "null",
                            "boolean"
                        ],
                        "id": "samples_on_rows"
                    }
                ],
                "outputs": [
                    {
                        "type": "Directory",
                        "id": "resdir"
                    }
                ]
            },
            "in": [
                {
                    "source": "data_matrix",
                    "id": "data_matrix"
                },
                {
                    "source": "separator",
                    "id": "separator"
                },
                {
                    "source": "index_col",
                    "id": "index_col"
                },
                {
                    "source": "gmt_filepath",
                    "id": "gmt_filepath"
                },
                {
                    "source": "outdir",
                    "id": "outdir"
                },
                {
                    "source": "samples_on_rows",
                    "id": "samples_on_rows"
                }
            ],
            "out": [
                "resdir"
            ],
            "id": "abstract_cosifer"
        }
    ],
    "requirements": []
}
