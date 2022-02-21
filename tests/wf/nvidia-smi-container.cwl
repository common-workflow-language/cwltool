cwlVersion: v1.2
class: CommandLineTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  cwltool:CUDARequirement:
    cudaVersionMin: "1.0"
    cudaComputeCapability: "1.0"
  DockerRequirement:
    dockerPull: "nvidia/cuda:11.4.2-runtime-ubuntu20.04"
inputs: []
outputs: []
# Assume this will exit non-zero (resulting in a failing test case) if
# nvidia-smi doesn't detect any devices.
baseCommand: "nvidia-smi"
