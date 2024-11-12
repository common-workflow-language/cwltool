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
  sleep_time: {type: int, default: 3333}
  n_sleepers: {type: int, default: 4}


steps:
  roulette:
    doc: |
      This step produces a boolean array with exactly one true value
      whose index is assigned at random.
    in: {n_sleepers: n_sleepers}
    out: [mask]
    run:
      class: ExpressionTool
      inputs: {n_sleepers: {type: int}}
      outputs: {mask: {type: "boolean[]"}}
      expression: |
        ${
          var mask = Array(inputs.n_sleepers).fill(false);
          var spin = Math.floor(Math.random() * inputs.n_sleepers);
          mask[spin] = true;
          return {"mask": mask}
        }

  scatter_step:
    doc: |
      This step starts several parallel jobs that each sleep for
      sleep_time seconds. The job whose k_mask value is true will
      self-terminate early, thereby activating the kill switch.
    in:
      time: sleep_time
      k_mask: roulette/mask
    scatter: k_mask
    out: [placeholder]
    run:
      class: CommandLineTool
      requirements:
        ToolTimeLimit:
          timelimit: '${return inputs.k_mask ? 5 : inputs.time + 5}'  # 5 is an arbitrary value
      baseCommand: sleep
      inputs:
        time: {type: int, inputBinding: {position: 1}}
        k_mask: {type: boolean}
      outputs:
        placeholder: {type: string, outputBinding: {outputEval: $("foo")}}

  dangling_step:
    doc: |
      This step should never run. It confirms that additional jobs aren't
      submitted and allowed to run to completion after the kill switch has
      been set. The input force_downstream_order ensures that this step
      doesn't run before scatter_step completes.
    in:
      force_downstream_order: scatter_step/placeholder
      time: sleep_time
    out: []
    run:
      class: CommandLineTool
      baseCommand: sleep
      inputs:
        time: {type: int, inputBinding: {position: 1}}
      outputs: {}


outputs:
  roulette_mask:
    type: boolean[]
    outputSource: roulette/mask
