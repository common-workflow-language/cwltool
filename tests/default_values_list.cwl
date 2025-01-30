#!/usr/bin/env cwl-runner
# From https://github.com/common-workflow-language/cwltool/issues/1632

cwlVersion: v1.2
class: CommandLineTool

baseCommand: [cat]

stdout: "cat_file"

inputs:
  file_paths:
    type: string[]?
    inputBinding:
        position: 1
    default: ["/home/bart/cwl_test/test1"]

outputs:
  output:
    type: stdout
