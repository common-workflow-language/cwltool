class: CommandLineTool
cwlVersion: cwl:draft-4.dev3
inputs:
  bar:
    type: Any
    default: {
          "baz": "zab1",
          "b az": 2,
          "b'az": true,
          'b"az': null,
          "buz": ['a', 'b', 'c']
        }

outputs: {"$import": params_inc.yml}

baseCommand: "true"
