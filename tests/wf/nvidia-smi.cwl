cwlVersion: v1.2
class: CommandLineTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  cwltool:CUDARequirement:
    cudaVersionMin: "1.0"
    cudaComputeCapabilityMin: "1.0"
  DockerRequirement:
    dockerPull: "nvidia/cuda:11.4.2-runtime-ubuntu20.04"
inputs: []
outputs: []
baseCommand: "nvidia-smi"
