#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: Workflow
$namespaces:
  cwltool: http://commonwl.org/cwltool#
hints:
  "cwltool:Secrets":
    secrets: [pw]
  DockerRequirement:
    dockerPull: docker.io/debian:stable-slim
inputs:
  pw: string
outputs:
  out:
    type: File
    outputSource: step1/out
steps:
  step1:
    in:
      pw: pw
    out: [out]
    run: secret_job.cwl
