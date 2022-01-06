{
    "$graph": [
        {
            "class": "Operation",
            "requirements": [
                {
                    "dockerPull": "docker.io/tsenit/cosifer:b4d5af45d2fc54b6bff2a9153a8e9054e560302e",
                    "class": "DockerRequirement"
                }
            ],
            "inputs": [
                {
                    "type": "File",
                    "id": "#abstract-cosifer.cwl/data_matrix"
                },
                {
                    "type": [
                        "null",
                        "File"
                    ],
                    "id": "#abstract-cosifer.cwl/gmt_filepath"
                },
                {
                    "type": [
                        "null",
                        "int"
                    ],
                    "id": "#abstract-cosifer.cwl/index_col"
                },
                {
                    "type": [
                        "null",
                        "string"
                    ],
                    "id": "#abstract-cosifer.cwl/outdir"
                },
                {
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "id": "#abstract-cosifer.cwl/samples_on_rows"
                },
                {
                    "type": [
                        "null",
                        "string"
                    ],
                    "doc": "The separator used in the data_matrix file",
                    "id": "#abstract-cosifer.cwl/separator"
                }
            ],
            "id": "#abstract-cosifer.cwl",
            "outputs": [
                {
                    "type": "Directory",
                    "id": "#abstract-cosifer.cwl/resdir"
                }
            ]
        },
        {
            "class": "Workflow",
            "id": "#main",
            "label": "abstract-cosifer-workflow",
            "inputs": [
                {
                    "type": "File",
                    "doc": "Gene expression data matrix",
                    "id": "#main/data_matrix"
                },
                {
                    "type": [
                        "null",
                        "File"
                    ],
                    "doc": "Optional GMT file to perform inference on multiple gene sets",
                    "id": "#main/gmt_filepath"
                },
                {
                    "type": [
                        "null",
                        "int"
                    ],
                    "doc": "Column index in the data. Defaults to None, a.k.a., no index",
                    "id": "#main/index_col"
                },
                {
                    "type": "string",
                    "doc": "Path to the output directory",
                    "id": "#main/outdir"
                },
                {
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "doc": "Flag that indicates that data contain the samples on rows. Defaults to False.",
                    "id": "#main/samples_on_rows"
                },
                {
                    "type": [
                        "null",
                        "string"
                    ],
                    "doc": "Separator for the data. Defaults to .",
                    "id": "#main/separator"
                }
            ],
            "outputs": [
                {
                    "type": "Directory",
                    "outputSource": "#main/abstract_cosifer/resdir",
                    "id": "#main/resdir"
                }
            ],
            "steps": [
                {
                    "run": "#abstract-cosifer.cwl",
                    "in": [
                        {
                            "source": "#main/data_matrix",
                            "id": "#main/abstract_cosifer/data_matrix"
                        },
                        {
                            "source": "#main/gmt_filepath",
                            "id": "#main/abstract_cosifer/gmt_filepath"
                        },
                        {
                            "source": "#main/index_col",
                            "id": "#main/abstract_cosifer/index_col"
                        },
                        {
                            "source": "#main/outdir",
                            "id": "#main/abstract_cosifer/outdir"
                        },
                        {
                            "source": "#main/samples_on_rows",
                            "id": "#main/abstract_cosifer/samples_on_rows"
                        },
                        {
                            "source": "#main/separator",
                            "id": "#main/abstract_cosifer/separator"
                        }
                    ],
                    "out": [
                        "#main/abstract_cosifer/resdir"
                    ],
                    "id": "#main/abstract_cosifer"
                }
            ]
        }
    ],
    "cwlVersion": "v1.2"
}
