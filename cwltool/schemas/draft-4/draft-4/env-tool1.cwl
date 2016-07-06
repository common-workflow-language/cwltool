class: CommandLineTool
cwlVersion: cwl:draft-4.dev3
inputs:
  in: string
outputs:
  out:
    type: File
    outputBinding:
      glob: out

requirements:
  EnvVarRequirement:
    envDef:
      TEST_ENV: $(inputs.in)

baseCommand: ["/bin/bash", "-c", "echo $TEST_ENV"]

stdout: out
