#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: Workflow
inputs:
  inp: File
  ex: string

requirements:
  ResourceRequirement:
      ramMin: 128
      ramMax: 64

outputs:
  classout:
    type: File
    outputSource: argument/classfile

steps:
  untar:
    run: tar-param.cwl
    in:
      tarfile: inp
      extractfile: ex
    out: [example_out]
    requirements:
      ResourceRequirement:
          ramMin: 64
          ramMax: 128

  argument:
    run: arguments.cwl
    in:
      src: untar/example_out
    out: [classfile]
