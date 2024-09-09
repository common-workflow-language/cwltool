#!/usr/bin/env cwl-runner

cwlVersion: v1.2
class: Workflow
requirements:
  ScatterFeatureRequirement: {}
  InlineJavascriptRequirement: {}
  StepInputExpressionRequirement: {}


doc: |
  This workflow tests the optional argument --on-error kill.
  MultithreadedJobExecutor() or --parallel should be used.
  A successful run should:
    1) Finish in (much) less than sleep_time seconds.
    2) Return outputs produced by successful steps.


inputs:
  sleep_time: { type: int, default: 33 }
  n_sleepers: { type: int?, default: 5 }


steps:
  make_array:
    doc: |
      This step produces an array of sleep_time values to be used
      as inputs for the scatter_step. The array also serves as the
      workflow output which should be collected despite the 
      kill switch triggered in the kill step below.
    in: { sleep_time: sleep_time, n_sleepers: n_sleepers }
    out: [ times ]
    run:
      class: ExpressionTool
      inputs:
          sleep_time: { type: int }
          n_sleepers: { type: int }
      outputs: { times: { type: "int[]" } }
      expression: |
        ${ return {"times": Array(inputs.n_sleepers).fill(inputs.sleep_time)} }

  scatter_step:
    doc: |
      This step starts several parallel jobs that each sleep for
      sleep_time seconds.
    in:
      time: make_array/times
    scatter: time
    out: [ ]
    run:
      class: CommandLineTool
      baseCommand: sleep
      inputs:
        time: { type: int, inputBinding: { position: 1 } }
      outputs: { }

  kill:
    doc: |
      This step waits a few seconds and selects a random scatter_step job to kill. 
      When `--on-error kill` is used, the runner should respond by terminating all 
      remaining jobs and exiting. This means the workflow's overall runtime should be 
      much less than max(sleep_time). The input force_upstream_order ensures that 
      this step runs after make_array, and therefore roughly parallel to scatter_step.
    in:
      force_upstream_order: make_array/times
      sleep_time: sleep_time
      search_str:
        valueFrom: $("sleep " + inputs.sleep_time)
    out: [ pid ]
    run: ../process_roulette.cwl

  dangling_step:
    doc: |
      This step should never run. It confirms that additional jobs aren't
      submitted and allowed to run to completion after the kill switch has
      been set. The input force_downstream_order ensures that this step runs
      after the kill step.
    in:
      force_downstream_order: kill/pid
      time: sleep_time
    out: [ ]
    run:
      class: CommandLineTool
      baseCommand: sleep
      inputs:
        time: { type: int, inputBinding: { position: 1 } }
      outputs: { }


outputs:
  instructed_sleep_times:
    type: int[]
    outputSource: make_array/times
