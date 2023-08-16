cwlVersion: v1.2
class: CommandLineTool
baseCommand: echo
inputs:
  letters:
    type: string[][]
    inputBinding:
      position: 1
stdout: echo.txt
outputs:
  echo: stdout
