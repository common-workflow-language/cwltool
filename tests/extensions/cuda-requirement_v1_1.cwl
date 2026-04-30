#!/usr/bin/env cwl-runner
cwlVersion: v1.1
class: CommandLineTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  cwltool:CUDARequirement:
    cudaVersionMin: "1.0"
    cudaComputeCapability: "1.0"
    cudaDeviceCountMin: $(inputs.gpus)
inputs:
  gpus:
    type: int
    default: 1
outputs: []
baseCommand: "nvidia-smi"