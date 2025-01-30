#!/usr/bin/env cwl-runner
cwlVersion: v1.1
$graph:
  - class: CommandLineTool
    id: makebzz
    inputs: []
    baseCommand: touch
    outputs:
      bzz:
        type: File
        outputBinding:
          glob: bzz
    arguments: [ bzz ]
  - class: Workflow
    id: main
    inputs: []
    outputs:
      b1:
        type: File
        outputSource: step1/bzz
      b2:
        type: File
        outputSource: step2/bzz
    steps:
      step1:
        in: {}
        out: [bzz]
        run: '#makebzz'
      step2:
        in: {}
        out: [bzz]
        run: '#makebzz'
