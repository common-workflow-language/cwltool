#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs: []
baseCommand: [ bash, -c ]
arguments:
# - "mkdir foo; echo 42 > foo/bar; ln -s bar foo/baz"
 - "mkdir foo; echo 42 > foo/bar; ln -s $PWD/foo/bar foo/baz"
# - "mkdir foo; ln -s $PWD/foo/bar foo/baz ; echo 42 > foo/bar"
outputs:
  result:
    type: Directory
    outputBinding:
      glob: foo
