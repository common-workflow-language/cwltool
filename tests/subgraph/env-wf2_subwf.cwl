#!/usr/bin/env cwl-runner
class: Workflow
cwlVersion: v1.2

inputs:
    in: string

outputs:
    out:
      type: File
      outputSource: sub_wf/out

requirements:
  SubworkflowFeatureRequirement: {}
  EnvVarRequirement:
    envDef:
      TEST_ENV: override_super

steps:
  sub_wf:
    run: env-wf2.cwl
    in:
      in: in
    out: [out]
