#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool
$namespaces:
  cwltool: http://commonwl.org/cwltool#
requirements:
  cwltool:Secrets:
    secrets: [pw]
inputs:
  pw: string
outputs:
  out: stdout
arguments: [cat, example.conf]
