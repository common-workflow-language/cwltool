#!/usr/bin/env cwl-runner
class: CommandLineTool
cwlVersion: v1.2
requirements:
  EnvVarRequirement:
    envDef:
      LC_ALL: C
  DockerRequirement:
    dockerPull: docker.io/debian:stable-slim
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
      - entry: $(inputs.eleventh)  # array of Files
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
  eleventh: File[]
outputs:
  out:
    type: Directory
    outputBinding:
      glob: .
  log: stdout
stdout: log.txt
baseCommand: [bash, -c]
arguments:
  - |
    find . | grep -v '\.docker' | sort
    find /my_path | sort
    find /my_other_path | sort
    echo "a" > first_writable_file
    echo "b" > /my_path/third_writable_file
    touch fifth_writable_directory/c
    touch /my_path/seventh_writable_directory/d
    find . | grep -v '\.docker' | sort
    find /my_path | sort
    find /my_other_path | sort
