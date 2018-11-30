import pytest

from cwltool.command_line_tool import CommandLineTool
from cwltool.context import LoadingContext


snippet = {
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
                                    "anon_enum_inside_array.cwl#first/species/mus_musculus"
                                ]
                            },
                            "null"
                        ],
                        "name": "anon_enum_inside_array.cwl#first/species"
                    }
                ]
            },
            "id": "anon_enum_inside_array.cwl#first"
        },
        {
            "type": [
                "null",
                {
                    "type": "enum",
                    "symbols": [
                        "anon_enum_inside_array.cwl#second/homo_sapiens",
                        "anon_enum_inside_array.cwl#second/mus_musculus"
                    ]
                }
            ],
            "id": "anon_enum_inside_array.cwl#second"
        }
    ],
    "baseCommand": "echo",
    "outputs": [],
    "id": "anon_enum_inside_array.cwl",
}

def test_anon_types():
    CommandLineTool(snippet, LoadingContext())
