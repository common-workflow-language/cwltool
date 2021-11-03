{
    "$graph": [
        {
            "class": "CommandLineTool",
            "inputs": [
                {
                    "type": "string",
                    "id": "#env-tool2.cwl/in"
                }
            ],
            "hints": [
                {
                    "envDef": [
                        {
                            "envValue": "$(inputs.in)",
                            "envName": "TEST_ENV"
                        }
                    ],
                    "class": "EnvVarRequirement"
                }
            ],
            "baseCommand": [
                "/bin/sh",
                "-c",
                "echo $TEST_ENV"
            ],
            "stdout": "out",
            "id": "#env-tool2.cwl",
            "outputs": [
                {
                    "type": "File",
                    "outputBinding": {
                        "glob": "out"
                    },
                    "id": "#env-tool2.cwl/out"
                }
            ]
        },
        {
            "class": "Workflow",
            "inputs": [
                {
                    "type": "string",
                    "id": "#env-wf2.cwl/in"
                }
            ],
            "outputs": [
                {
                    "type": "File",
                    "outputSource": "#env-wf2.cwl/step1/out",
                    "id": "#env-wf2.cwl/out"
                }
            ],
            "requirements": [
                {
                    "envDef": [
                        {
                            "envValue": "override",
                            "envName": "TEST_ENV"
                        }
                    ],
                    "class": "EnvVarRequirement"
                }
            ],
            "steps": [
                {
                    "run": "#env-tool2.cwl",
                    "in": [
                        {
                            "source": "#env-wf2.cwl/in",
                            "id": "#env-wf2.cwl/step1/in"
                        }
                    ],
                    "out": [
                        "#env-wf2.cwl/step1/out"
                    ],
                    "id": "#env-wf2.cwl/step1"
                }
            ],
            "id": "#env-wf2.cwl"
        },
        {
            "class": "Workflow",
            "inputs": [
                {
                    "type": "string",
                    "id": "#main/in"
                }
            ],
            "outputs": [
                {
                    "type": "File",
                    "outputSource": "#main/sub_wf/out",
                    "id": "#main/out"
                }
            ],
            "requirements": [
                {
                    "envDef": [
                        {
                            "envValue": "override_super",
                            "envName": "TEST_ENV"
                        }
                    ],
                    "class": "EnvVarRequirement"
                },
                {
                    "class": "SubworkflowFeatureRequirement"
                }
            ],
            "steps": [
                {
                    "run": "#env-wf2.cwl",
                    "in": [
                        {
                            "source": "#main/in",
                            "id": "#main/sub_wf/in"
                        }
                    ],
                    "out": [
                        "#main/sub_wf/out"
                    ],
                    "id": "#main/sub_wf"
                }
            ],
            "id": "#main"
        }
    ],
    "cwlVersion": "v1.2"
}