{
    "$graph": [
        {
            "class": "Operation",
            "requirements": [
                {
                    "dockerPull": "tsenit/cosifer:b4d5af45d2fc54b6bff2a9153a8e9054e560302e",
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
            "outputs": [
                {
                    "type": "Directory",
                    "id": "#abstract-cosifer.cwl/resdir"
                }
            ],
            "id": "#abstract-cosifer.cwl"
        },
        {
            "class": "Workflow",
            "id": "#main",
            "label": "abstract-cosifer-workflow",
            "inputs": [
                {
                    "type": "File",
                    "doc": "Gene expression data matrix",
                    "id": "#data_matrix"
                },
                {
                    "type": [
                        "null",
                        "File"
                    ],
                    "doc": "Optional GMT file to perform inference on multiple gene sets",
                    "id": "#gmt_filepath"
                },
                {
                    "type": [
                        "null",
                        "int"
                    ],
                    "doc": "Column index in the data. Defaults to None, a.k.a., no index",
                    "id": "#index_col"
                },
                {
                    "type": "string",
                    "doc": "Path to the output directory",
                    "id": "#outdir"
                },
                {
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "doc": "Flag that indicates that data contain the samples on rows. Defaults to False.",
                    "id": "#samples_on_rows"
                },
                {
                    "type": [
                        "null",
                        "string"
                    ],
                    "doc": "Separator for the data. Defaults to .",
                    "id": "#separator"
                }
            ],
            "outputs": [
                {
                    "type": "Directory",
                    "outputSource": "#/abstract_cosifer/resdir",
                    "id": "#resdir"
                }
            ],
            "steps": [
                {
                    "run": "#abstract-cosifer.cwl",
                    "in": [
                        {
                            "source": "#data_matrix",
                            "id": "#abstract_cosifer/data_matrix"
                        },
                        {
                            "source": "#gmt_filepath",
                            "id": "#abstract_cosifer/gmt_filepath"
                        },
                        {
                            "source": "#index_col",
                            "id": "#abstract_cosifer/index_col"
                        },
                        {
                            "source": "#outdir",
                            "id": "#abstract_cosifer/outdir"
                        },
                        {
                            "source": "#samples_on_rows",
                            "id": "#abstract_cosifer/samples_on_rows"
                        },
                        {
                            "source": "#separator",
                            "id": "#abstract_cosifer/separator"
                        }
                    ],
                    "out": [
                        "#/abstract_cosifer/resdir"
                    ],
                    "id": "#abstract_cosifer"
                }
            ]
        }
    ],
    "cwlVersion": "v1.2"
}