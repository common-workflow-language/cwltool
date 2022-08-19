{
  "baseCommand": [
    "cat"
  ],
  "class": "CommandLineTool",
  "cwlVersion": "v1.2",
  "id": "cat-tool-shortcut.cwl",
  "inputs": [
    {
      "id": "file1",
      "type": "stdin"
    }
  ],
  "outputs": [
    {
      "id": "output",
      "outputBinding": {
        "glob": "output"
      },
      "type": "File"
    }
  ],
  "requirements": [
    {
      "class": "DockerRequirement",
      "dockerPull": "debian:stable-slim"
    }
  ],
  "stdout": "output"
}
