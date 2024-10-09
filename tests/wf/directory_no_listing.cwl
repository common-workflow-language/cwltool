#!/usr/bin/env cwl-runner
cwlVersion: v1.2
class: Workflow

doc: >
    Inspect provided directory and return filenames.
    Generate a new directory and return it (including content).

hints:
  - class: DockerRequirement
    dockerPull: docker.io/debian:stable-slim

inputs:
    dir_deep_listing:
        type: Directory
        loadListing: deep_listing
    dir_no_listing:
        type: Directory
        loadListing: no_listing
    dir_no_info:
        type: Directory


steps:
    ls:
        in:
            dir: dir_deep_listing
            ignore: dir_no_listing
        out:
            [listing]
        run:
            class: CommandLineTool
            baseCommand: ls
            inputs:
                dir:
                    type: Directory
                    inputBinding:
                        position: 1
#                ignore:
#                    type: Directory
#                    inputBinding:
#                        position: 2
            outputs:
                listing:
                    type: stdout

    generate:
        in: []
        out:
            [dir1]
        run:
            class: CommandLineTool
            requirements:
                ShellCommandRequirement: {}
                LoadListingRequirement:
                    loadListing: deep_listing

            arguments:
            - shellQuote: false
              valueFrom: >
                    pwd;
                    mkdir -p dir1/x/y;
                    echo -n x > dir1/x.txt;
                    echo -n y > dir1/x/y.txt;
                    echo -n z > dir1/x/y/z.txt;
            inputs: []
            outputs:
                dir1:
                    type: Directory
                    outputBinding:
                        glob: "dir1"

outputs:
    output_1:
        type: File
        outputSource: ls/listing
    output_2:
        type: Directory
        outputSource: generate/dir1
