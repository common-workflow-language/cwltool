#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.0
requirements:
  DockerRequirement:
    dockerPull: debian
  InitialWorkDirRequirement:
    listing:
      - entry: $(inputs.first)
        entryname: first_writable_file
        writable: true
      - entry: $(inputs.second)
        entryname: second_read_only_file
        writable: false
      - entry: $(inputs.third)
        entryname: /my_path/third_writable_file
        writable: true
      - entry: $(inputs.fourth)
        entryname: /my_other_path/fourth_read_only_file
        writable: false
      - entry: $(inputs.fifth)
        entryname: fifth_writable_directory
        writable: true
      - entry: $(inputs.sixth)
        entryname: sixth_read_only_directory
        writable: false
      - entry: $(inputs.seventh)
        entryname: /my_path/seventh_writable_directory
        writable: true
      - entry: $(inputs.eighth)
        entryname: /my_other_path/eighth_read_only_directory
        writable: false
      - entry: $(inputs.ninth)
        entryname: nineth_writable_directory_literal
        writable: true
      - entry: $(inputs.tenth)
        entryname: /my_path/tenth_writable_directory_literal
        writable: true
      - entry: baz
        entryname: /my_path/my_file_literal
inputs:
  first: File
  second: File
  third: File
  fourth: File
  fifth: Directory
  sixth: Directory
  seventh: Directory
  eighth: Directory
  ninth:
    type: Directory
    default:
      class: Directory
      basename: foo
      listing: []
  tenth:
    type: Directory
    default:
      class: Directory
      basename: bar
      listing: []
outputs:
  out:
    type: Directory
    outputBinding:
      glob: .
baseCommand: [bash, -c]
arguments:
  - |
    find .
    find /my_path
    find /my_other_path
    echo "a" > first_writable_file
    echo "b" > /my_path/third_writable_file
    touch fifth_writable_directory/c
    touch /my_path/seventh_writable_directory/d

