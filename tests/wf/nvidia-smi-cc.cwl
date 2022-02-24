cwlVersion: v1.2
class: CommandLineTool
$namespaces:
  cwltool: "http://commonwl.org/cwltool#"
requirements:
  cwltool:CUDARequirement:
    cudaVersionMin: "1.0"
    cudaComputeCapability: ["1.0", "2.0", "3.0"]
    cudaDeviceCountMin: $(inputs.gpus)
inputs:
  gpus:
    type: int
    default: 1
outputs: []
# Assume this will exit non-zero (resulting in a failing test case) if
# nvidia-smi doesn't detect any devices.
baseCommand: "nvidia-smi"
