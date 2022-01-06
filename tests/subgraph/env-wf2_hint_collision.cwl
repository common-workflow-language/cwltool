#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.2

inputs:
    in: string

outputs:
    out:
      type: File
      outputSource: step1/out

hints:
  EnvVarRequirement:
    envDef:
      TEST_ENV: override

steps:
  step1:
    run: env-tool2.cwl
    in:
      in: in
    out: [out]
