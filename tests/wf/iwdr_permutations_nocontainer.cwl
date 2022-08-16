#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.2
requirements:
  InitialWorkDirRequirement:
    listing:
      - entry: $(inputs.first)
        entryname: first_writable_file
        writable: true
      - entry: $(inputs.second)
        entryname: second_read_only_file
        writable: false
      - entry: $(inputs.fifth)
        entryname: fifth_writable_directory
        writable: true
      - entry: $(inputs.sixth)
        entryname: sixth_read_only_directory
        writable: false
      - entry: $(inputs.ninth)
        entryname: nineth_writable_directory_literal
        writable: true
inputs:
  first: File
  second: File
  fifth: Directory
  sixth: Directory
  ninth:
    type: Directory
    default:
      class: Directory
      basename: foo
      listing: []
outputs:
  out:
    type: Directory
    outputBinding:
      glob: .
baseCommand: [bash, -c]
arguments:
  - |
    find . | grep -v '\.docker' | sort
    echo "a" > first_writable_file
    touch fifth_writable_directory/c
