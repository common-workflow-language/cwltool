#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.2

requirements:
  ResourceRequirement:
      ramMin: 254.1
      ramMax: 254.9
      tmpdirMin: 255.1
      tmpdirMax: 255.9
      outdirMin: 256.1
      outdirMax: 256.9

inputs: []

outputs:
  output: stdout

baseCommand: echo

stdout: values.txt

arguments: [ $(runtime.ram), $(runtime.tmpdirSize), $(runtime.outdirSize) ]
