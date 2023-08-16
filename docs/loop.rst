=====
Loops
=====

The ``cwltool:Loop`` requirement enables workflow-level looping of a step. It is valid only under ``requirements`` of a ``WorkflowStep``. Unlike other CWL requirements, Loop requirement is not propagated to inner steps.

The ``cwltool:Loop`` is not compatible with ``scatter`` and ``when``. Combining a ``cwltool:Loop`` requirement with a ``scatter`` or a ``when`` clause in the same step will produce an error.

The loop condition
==================

The ``loopWhen`` field controls loop termination. It is an expansion of the CWL v1.2 ``when`` construct, which controls conditional execution. This is an expression that must be evaluated with ``inputs`` bound to the step input object and outputs produced in the last step execution, and returns a boolean value. It is an error if this expression returns a value other than ``true`` or ``false``. For example:

.. code:: yaml

  example:
    run:
      class: ExpressionTool
      inputs:
        i1: int
      outputs:
        o1: int
      expression: >
        ${return {'o1': inputs.i1 + 1};}
    in:
      i1: i1
    out: [o1]
    requirements:
      cwltool:Loop:
        loopWhen: $(inputs.i1 < 10)
        loop:
          i1: o1
        outputMethod: last

This loop executes untile the counter ``i1`` reaches the value of 10, and then terminates. Note that if the ``loopWhen`` condition evaluates to ``false`` prior to the first iteration, the loop is skipped. The value assumed by the output fields depends on the specified ``outputMethod``, as described below.

The loop field
==============

The ``loop`` field defines the input parameters of the loop iterations after the first one (inputs of the first iteration are the step input parameters). If no loop rule is specified for a given step ``in`` field, the initial value is kept constant among all iterations.

The ``LoopInput`` is basically a reduced version of the ``WorkflowStepInput`` structure with the possibility to include outputs of the previous step execution in the ``valueFrom`` expression.

.. list-table::
   :header-rows: 1

   * - Field
     - Required
     - Type
     - Description
   * - ``id``
     - optional
     - string
     - It must reference the ``id`` of one of the elements in the ``in`` field of the step.
   * - ``loopSource``
     - optional
     - string? | string[]?
     - Specifies one or more of the step output parameters that will provide input to the loop iterations after the first one (inputs of the first iteration are the step input parameters).
   * - ``linkMerge``
     - optional
     - LinkMergeMethod
     - The method to use to merge multiple inbound links into a single array. If not specified, the default method is ``merge_nested``.
   * - ``pickValue``
     - optional
     - PickValueMethod
     - The method to use to choose non-null elements among multiple sources.
   * - ``valueFrom``
     - optional
     - string | Expression
     - To use ``valueFrom``, StepInputExpressionRequirement must be specified in the workflow or workflow step requirements. If ``valueFrom`` is a constant string value, use this as the value for this input parameter. If ``valueFrom`` is a parameter reference or expression, it must be evaluated to yield the actual value to be assigned to the input field. The ``self`` value in the parameter reference or expression must be ``null`` if there is no ``loopSource`` field, or the value of the parameter(s) specified in the ``loopSource`` field. The value of ``inputs`` in the parameter reference or expression must be the input object to the previous iteration of the workflow step (or the initial inputs for the first iteration).

Loop output modes
=================

The ``outputMethod`` field specifies the desired method of dealing with loop outputs. It behaves similarly to the ``scatterMethod`` field. For the sake of simplicity, there can be a single ``outputMethod`` field for each step instead of specifying a different behaviour for each output element. The ``outputMethod`` field can take two possible values: ``last`` or ``all``.

The ``last`` output mode propagates only the last computed element to the subsequent steps when the loop terminates. When a loop with an ``outputMethod`` equal to ``last`` is skipped, each output assumes a ``null`` value.

This is the most recurrent behaviour and it is typical of the optimization processes, when a step must iterate until a desired precision is reached. For example:

.. code:: yaml

  optimization:
    in:
      a: a
      prev_a:
        default: ${ return inputs.a - (2 * inputs.threshold) }
      threshold: threshold
    run: optimize.cwl
    out: [a]
    requirements:
      cwltool:Loop:
        loopWhen: ${ return (inputs.a - inputs.prev_a) > inputs.threshold)
        loop:
          a: a
          prev_a:
            valueFrom: $(inputs.a)
        outputMethod: last

This loop keeps optimizing the initial ``a`` value until the error value falls below a given (constant) ``threshold``. Then, the last values of ``a`` will be propagated.

The ``all`` output mode propagates a single array with all output values to the subsequent steps when the loop terminates. When a loop with an ``outputMethod`` equal to ``all`` is skipped, each output assumes a ``[]`` value.

This behaviour is needed when a recurrent simulation produces loop-carried results, but the subsequent steps need to know the total amount of computed values to proceed. For example:

.. code:: yaml

  simulation:
    in:
      a: a
      day:
        default: 0
      max_day: max_day
    run: simulate.cwl
    out: [a]
    requirements:
      cwltool:Loop:
        loopWhen: ${ return inputs.day < inputs.max_day }
        loop:
          a: a
          day:
            valueFrom: $(inputs.day + 1)
        outputMethod: all

In this case, subsequent steps can start processing outputs even before the ``simulation`` step terminates. When a loop with an ``outputMethod`` equal to ``last`` is skipped, each output assumes a ``null`` value.

Loop-independent iterations
===========================

If a ``cwltool:Loop`` comes with loop-independent iterations, i.e. if each iteration does not depend on the result produced by the previous ones, all iterations can be processed concurrently. For example:

.. code:: yaml

  example:
    run: inner.cwl
    in:
      i1: i1
    out: [o1]
    requirements:
      cwltool:Loop:
        loopWhen: $(inputs.i1 < 10)
        loop:
          i1:
            valueFrom: $(inputs.i1 + 1)
        outputMethod: all

Since each iteration of this loop only depends on the input field ``i1``, all its iterations can be processed in parallel if there is enough computing power.
