#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.0.dev4

inputs:
    in: string

outputs:
    out:
      type: File
      outputSource: step1/out

requirements:
  - class: SubworkflowFeatureRequirement
  - class: EnvVarRequirement
    envDef:
      TEST_ENV: override

steps:
  step1:
    run: env-tool2.cwl
    in:
      in: in
    out: [out]
