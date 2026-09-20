#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: Workflow

inputs: []

outputs:
  env:
    type: File
    outputSource: env_step/env

steps:
  env_step:
    run: env-preserve-step-tool.cwl
    in: []
    out: [env]
    requirements:
      EnvVarRequirement:
        envDef:
          TMPDIR: /custom/tmpdir
