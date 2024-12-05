#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: CommandLineTool


doc: |
  This tool selects a random process whose associated command matches 
  search_str, terminates it, and reports the PID of the terminated process. 
  The search_str supports regex. Example search_strs:
  - "sleep"
  - "sleep 33"
  - "sleep [0-9]+"


baseCommand: [ 'bash', '-c' ]
arguments:
  - |
    sleep $(inputs.delay)
    pid=\$(ps -ef | grep '$(inputs.search_str)' | grep -v grep | awk '{print $2}' | shuf | head -n 1)
    echo "$pid" | tee >(xargs kill -SIGTERM)
inputs:
  search_str:
    type: string
  delay:
    type: int?
    default: 3
stdout: "pid.txt"
outputs:
  pid:
    type: string
    outputBinding:
      glob: pid.txt
      loadContents: true
      outputEval: $(self[0].contents)