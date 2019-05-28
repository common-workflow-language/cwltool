cwlVersion: v1.1
$graph:
  - class: CommandLineTool
    id: first
    inputs:
      in:
        type: Any
    outputs:
      out:
        type: string
        outputBinding:
          glob: out.txt
          loadContents: true
          outputEval: $(self[0].contents)
    baseCommand: [ echo, first ]
    stdout: out.txt
  - class: CommandLineTool
    id: '#main'
    inputs:
      in:
        type: Any
        inputBinding: {}
    outputs:
      out:
        type: string
        outputBinding:
          glob: out.txt
          loadContents: true
          outputEval: $(self[0].contents)
    baseCommand: echo
    stdout: out.txt
