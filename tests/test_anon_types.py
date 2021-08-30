from typing import cast

import pytest
from ruamel.yaml.comments import CommentedMap
from schema_salad.sourceline import cmap

from cwltool.command_line_tool import CommandLineTool
from cwltool.context import LoadingContext

snippet = cast(
    CommentedMap,
    cmap(
        [
            {
                "cwlVersion": "v1.0",
                "class": "CommandLineTool",
                "inputs": [
                    {
                        "type": {
                            "type": "record",
                            "fields": [
                                {
                                    "type": [
                                        {
                                            "type": "enum",
                                            "symbols": [
                                                "anon_enum_inside_array.cwl#first/species/homo_sapiens",
                                                "anon_enum_inside_array.cwl#first/species/mus_musculus",
                                            ],
                                        },
                                        "null",
                                    ],
                                    "name": "anon_enum_inside_array.cwl#first/species",
                                }
                            ],
                        },
                        "id": "anon_enum_inside_array.cwl#first",
                    },
                    {
                        "type": [
                            "null",
                            {
                                "type": "enum",
                                "symbols": [
                                    "anon_enum_inside_array.cwl#second/homo_sapiens",
                                    "anon_enum_inside_array.cwl#second/mus_musculus",
                                ],
                            },
                        ],
                        "id": "anon_enum_inside_array.cwl#second",
                    },
                ],
                "baseCommand": "echo",
                "outputs": [],
                "id": "anon_enum_inside_array.cwl",
            },
            {
                "cwlVersion": "v1.0",
                "class": "CommandLineTool",
                "requirements": [
                    {
                        "types": [
                            {
                                "name": "anon_enum_inside_array_inside_schemadef.cwl#vcf2maf_params",
                                "type": "record",
                                "fields": [
                                    {
                                        "type": [
                                            "null",
                                            {
                                                "type": "enum",
                                                "symbols": [
                                                    "anon_enum_inside_array_inside_schemadef.cwl#vcf2maf_params/ncbi_build/GRCh37",
                                                    "anon_enum_inside_array_inside_schemadef.cwl#vcf2maf_params/ncbi_build/GRCh38",
                                                    "anon_enum_inside_array_inside_schemadef.cwl#vcf2maf_params/ncbi_build/GRCm38",
                                                ],
                                            },
                                        ],
                                        "name": "anon_enum_inside_array_inside_schemadef.cwl#vcf2maf_params/ncbi_build",
                                    },
                                    {
                                        "type": [
                                            "null",
                                            {
                                                "type": "enum",
                                                "symbols": [
                                                    "anon_enum_inside_array_inside_schemadef.cwl#vcf2maf_params/species/homo_sapiens",
                                                    "anon_enum_inside_array_inside_schemadef.cwl#vcf2maf_params/species/mus_musculus",
                                                ],
                                            },
                                        ],
                                        "name": "anon_enum_inside_array_inside_schemadef.cwl#vcf2maf_params/species",
                                    },
                                ],
                            }
                        ],
                        "class": "SchemaDefRequirement",
                    }
                ],
                "inputs": [
                    {
                        "type": "anon_enum_inside_array_inside_schemadef.cwl#vcf2maf_params",
                        "id": "anon_enum_inside_array_inside_schemadef.cwl#first",
                    }
                ],
                "baseCommand": "echo",
                "outputs": [],
                "id": "anon_enum_inside_array_inside_schemadef.cwl",
            },
        ]
    ),
)


@pytest.mark.parametrize("snippet", snippet)
def test_anon_types(snippet: CommentedMap) -> None:
    CommandLineTool(snippet, LoadingContext())
