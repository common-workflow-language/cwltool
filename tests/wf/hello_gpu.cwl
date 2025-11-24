#!/usr/bin/env cwl-runner
cwlVersion: v1.0

$graph:

- class: Workflow
  id: main
  label: Test GPU
  doc: |
    Print GPU info.
  s:keywords: gpu
  s:softwareVersion: 0.1.0

  inputs: []

  outputs:
    echo:
      type: File
      outputSource: node_hello/echo

  steps:
    node_hello:
      in: []
      run: '#hello-cl'
      out:
      - echo

- class: CommandLineTool
  id: hello-cl
  s:softwareVersion: 1.0.0

  baseCommand: nvidia-smi
  arguments: []

  requirements:
    cwltool:CUDARequirement:
      cudaVersionMin: "12.0"
      cudaComputeCapability: "7.5"
      cudaDeviceCountMin: 1
      cudaDeviceCountMax: 4
  inputs: []

  outputs:
    echo:
      type: File
      outputBinding:
        glob: output.txt
  stdout: output.txt

$namespaces:
  cwltool: http://commonwl.org/cwltool#
  s: https://schema.org/
