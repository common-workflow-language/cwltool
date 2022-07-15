#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: Workflow

inputs: []

steps:
  # Create a test directory structure; could be done outside CWL and passed in as input.
  # This input directory should be left pristine.
  mkdirs:
    run:
      class: CommandLineTool
      baseCommand: [bash, '-c', 'mkdir dir dir/subdir && touch dir/subdir/file', '-']
      inputs: []
      outputs:
        mkdirs_out:
          type: Directory
          outputBinding:
            glob: dir
    in: []
    out: [mkdirs_out]

  # Given an input directory, emit a subdirectory as output.
  passthrough1:
    run:
      class: CommandLineTool
      requirements:
      - class: InitialWorkDirRequirement
        listing:
        - entry: $(inputs.passthrough1_in)
          writable: false
      baseCommand: ["true"]
      inputs:
        passthrough1_in:
          type: Directory
      outputs:
        passthrough1_subdir:
          type: Directory
          outputBinding:
            glob: $(inputs.passthrough1_in.basename)/subdir
    in:
      passthrough1_in: mkdirs/mkdirs_out
    out: [passthrough1_subdir]

  # Given a (sub-)directory, emit it unchanged.
  passthrough2:
    run:
      class: CommandLineTool
      requirements:
      - class: InitialWorkDirRequirement
        listing:
        - entry: $(inputs.passthrough2_in)
          writable: false
      baseCommand: ["true"]
      inputs:
        passthrough2_in:
          type: Directory
      outputs:
        passthrough2_subdir:
          type: Directory
          outputBinding:
            glob: $(inputs.passthrough2_in.basename)
    in:
      passthrough2_in: passthrough1/passthrough1_subdir
    out: [passthrough2_subdir]

outputs:
  out:
    type: Directory
    outputSource: passthrough2/passthrough2_subdir