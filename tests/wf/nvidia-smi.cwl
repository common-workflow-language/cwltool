cwlVersion: v1.2
class: CommandLineTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  cwltool:CUDARequirement:
    cudaVersionMin: "1.0"
    cudaComputeCapabilityMin: "1.0"
inputs: []
outputs: []
baseCommand: "nvidia-smi"
