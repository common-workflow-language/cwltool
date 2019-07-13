#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.1

requirements:
  ResourceRequirement:
      coresMin: $(inputs.special_file.size)
      coresMax: $(inputs.special_file.size)

inputs:
  special_file:
    type: File
    default:
      class: File
      location: special_file

outputs:
  output:
    type: stdout

baseCommand: echo

stdout: cores.txt

arguments: [ $(runtime.cores) ]
