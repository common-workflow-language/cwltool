#!/usr/bin/env cwl-runner
#
# This is a two-step workflow which uses "revtool" and "sorttool" defined above.
#
class: Workflow
doc: "Reverse the lines in a document, then sort those lines."
cwlVersion: v1.0

# Requirements & hints specify prerequisites and extensions to the workflow.
# In this example, DockerRequirement specifies a default Docker container
# in which the command line tools will execute.
hints:
  - class: DockerRequirement
    dockerPull: docker.io/debian:stable-slim


# The inputs array defines the structure of the input object that describes
# the inputs to the workflow.
#
# The "reverse_sort" input parameter demonstrates the "default" field.  If the
# field "reverse_sort" is not provided in the input object, the default value will
# be used.
inputs:
  workflow_input:
    type: File
    doc: "The input file to be processed."
    format: iana:text/plain
    default:
      class: File
      location: hello.txt
  reverse_sort:
    type: boolean
    default: true
    doc: "If true, reverse (descending) sort"

# The "outputs" array defines the structure of the output object that describes
# the outputs of the workflow.
#
# Each output field must be connected to the output of one of the workflow
# steps using the "outputSource" field.  Here, the parameter "sorted_output" of the
# workflow comes from the "sorted_output" output of the "sorted" step.
outputs:
  sorted_output:
    type: File
    outputSource: sorted/sorted_output
    doc: "The output with the lines reversed and sorted."

# The "steps" array lists the executable steps that make up the workflow.
# The tool to execute each step is listed in the "run" field.
#
# In the first step, the "in" field of the step connects the upstream
# parameter "workflow_input" of the workflow to the input parameter of the tool
# "revtool_input"
#
# In the second step, the "in" field of the step connects the output
# parameter "revtool_output" from the first step to the input parameter of the
# tool "sorted_input".
steps:
  rev:
    in:
      revtool_input: workflow_input
    out: [revtool_output]
    run: revtool.cwl

  sorted:
    in:
      sorted_input: rev/revtool_output
      reverse: reverse_sort
    out: [sorted_output]
    run: sorttool.cwl

$namespaces:
  iana: https://www.iana.org/assignments/media-types/
  s: http://schema.org/

$schemas:
 - https://schema.org/version/latest/schemaorg-current-https.rdf
 - empty2.ttl

s:dateCreated: 2020-10-08
