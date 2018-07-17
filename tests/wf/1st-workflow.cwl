#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: Workflow
inputs:
  inp: File
  ex: string

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

  argument:
    run: arguments.cwl
    in:
      src: untar/example_out
    out: [classfile]
