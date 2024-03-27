"""Test the prototype loop extension."""

import json
from io import StringIO
from typing import MutableMapping, MutableSequence

from cwltool.main import main

from .util import get_data


def test_validate_loop() -> None:
    """Affirm that a loop workflow validates with --enable-ext."""
    params = [
        "--enable-ext",
        "--validate",
        get_data("tests/loop/single-var-loop.cwl"),
    ]
    assert main(params) == 0


def test_validate_loop_fail_no_ext() -> None:
    """Affirm that a loop workflow does not validate when --enable-ext is missing."""
    params = [
        "--validate",
        get_data("tests/loop/single-var-loop.cwl"),
    ]
    assert main(params) == 1


def test_validate_loop_fail_scatter() -> None:
    """Affirm that a loop workflow does not validate if scatter and loop directives are on the same step."""
    params = [
        "--enable-ext",
        "--validate",
        get_data("tests/loop/invalid-loop-scatter.cwl"),
    ]
    assert main(params) == 1


def test_validate_loop_fail_when() -> None:
    """Affirm that a loop workflow does not validate if when and loop directives are on the same step."""
    params = [
        "--enable-ext",
        "--validate",
        get_data("tests/loop/invalid-loop-when.cwl"),
    ]
    assert main(params) == 1


def test_validate_loop_fail_no_loop_when() -> None:
    """Affirm that a loop workflow does not validate if no loopWhen directive is specified."""
    params = [
        "--enable-ext",
        "--validate",
        get_data("tests/loop/invalid-no-loopWhen.cwl"),
    ]
    assert main(params) == 1


def test_validate_loop_fail_on_workflow() -> None:
    """Affirm that a workflow does not validate if it contains a Loop requirement."""
    params = [
        "--enable-ext",
        "--validate",
        get_data("tests/loop/invalid-loop-workflow.cwl"),
    ]
    assert main(params) == 1


def test_validate_loop_fail_on_command_line_tool() -> None:
    """Affirm that a CommandLineTool does not validate if it contains a Loop requirement."""
    params = [
        "--enable-ext",
        "--validate",
        get_data("tests/loop/invalid-loop-command-line-tool.cwl"),
    ]
    assert main(params) == 1


def test_validate_loop_fail_on_expression_tool() -> None:
    """Affirm that an ExpressionTool does not validate if it contains a Loop requirement."""
    params = [
        "--enable-ext",
        "--validate",
        get_data("tests/loop/invalid-loop-expression-tool.cwl"),
    ]
    assert main(params) == 1


def test_validate_loop_fail_on_hint() -> None:
    """Affirm that a loop workflow does not validate if it contains a Loop hint."""
    params = [
        "--enable-ext",
        "--validate",
        get_data("tests/loop/invalid-loop-hint.cwl"),
    ]
    assert main(params) == 1


def test_loop_fail_non_boolean_loop_when() -> None:
    """Affirm that a loop workflow fails if loopWhen directive returns a non-boolean value."""
    params = [
        "--enable-ext",
        get_data("tests/loop/invalid-non-boolean-loopWhen.cwl"),
        get_data("tests/loop/two-vars-loop-job.yml"),
    ]
    assert main(params) == 1


def test_loop_single_variable() -> None:
    """Test a simple loop case with a single variable."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/single-var-loop.cwl"),
        get_data("tests/loop/single-var-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": 10}
    assert json.loads(stream.getvalue()) == expected


def test_loop_single_variable_no_iteration() -> None:
    """Test a simple loop case with a single variable and a false loopWhen condition."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/single-var-loop-no-iteration.cwl"),
        get_data("tests/loop/single-var-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": None}
    assert json.loads(stream.getvalue()) == expected


def test_loop_two_variables() -> None:
    """Test a loop case with two variables, which are both back-propagated between iterations."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/two-vars-loop.cwl"),
        get_data("tests/loop/two-vars-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": 10}
    assert json.loads(stream.getvalue()) == expected


def test_loop_two_variables_single_backpropagation() -> None:
    """Test loop with 2 variables, but when only one of them is back-propagated between iterations."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/two-vars-loop-2.cwl"),
        get_data("tests/loop/two-vars-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": 10}
    assert json.loads(stream.getvalue()) == expected


def test_loop_with_all_output_method() -> None:
    """Test a loop case with outputMethod set to all."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/all-output-loop.cwl"),
        get_data("tests/loop/single-var-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": [2, 3, 4, 5, 6, 7, 8, 9, 10]}
    assert json.loads(stream.getvalue()) == expected


def test_loop_with_all_output_method_no_iteration() -> None:
    """Test a loop case with outputMethod set to all and a false loopWhen condition."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/all-output-loop-no-iteration.cwl"),
        get_data("tests/loop/single-var-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected: MutableMapping[str, MutableSequence[int]] = {"o1": []}
    assert json.loads(stream.getvalue()) == expected


def test_loop_value_from() -> None:
    """Test a loop case with a variable generated by a valueFrom directive."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/value-from-loop.cwl"),
        get_data("tests/loop/two-vars-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": 10}
    assert json.loads(stream.getvalue()) == expected


def test_loop_value_from_fail_no_requirement() -> None:
    """Test workflow loop fails for valueFrom without StepInputExpressionRequirement."""
    params = [
        "--enable-ext",
        get_data("tests/loop/invalid-value-from-loop-no-requirement.cwl"),
        get_data("tests/loop/two-vars-loop-job.yml"),
    ]
    assert main(params) == 1


def test_loop_inside_scatter() -> None:
    """Test a loop subworkflow inside a scatter step."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/loop-inside-scatter.cwl"),
        get_data("tests/loop/loop-inside-scatter-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": [10, 10, 10, 10, 10]}
    assert json.loads(stream.getvalue()) == expected


def test_scatter_inside_loop() -> None:
    """Test a loop workflow with inside a scatter step."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/scatter-inside-loop.cwl"),
        get_data("tests/loop/loop-inside-scatter-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": [10, 11, 12, 13, 14]}
    assert json.loads(stream.getvalue()) == expected


def test_nested_loops() -> None:
    """Test a workflow with two nested loops."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/loop-inside-loop.cwl"),
        get_data("tests/loop/two-vars-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": [2, 3, 4]}
    assert json.loads(stream.getvalue()) == expected


def test_nested_loops_all() -> None:
    """Test a workflow with two nested loops, both with outputMethod set to all."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/loop-inside-loop-all.cwl"),
        get_data("tests/loop/two-vars-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": [[2], [2, 3], [2, 3, 4]]}
    assert json.loads(stream.getvalue()) == expected


def test_multi_source_loop_input() -> None:
    """Test a loop with two sources, which are selected through a pickValue directive."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/multi-source-loop.cwl"),
        get_data("tests/loop/single-var-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": [2, 3, 4, 5, 8, 11, 14, 17, 20]}
    assert json.loads(stream.getvalue()) == expected


def test_multi_source_loop_input_fail_no_requirement() -> None:
    """Test that a loop with two sources fails without MultipleInputFeatureRequirement."""
    params = [
        "--enable-ext",
        get_data("tests/loop/invalid-multi-source-loop-no-requirement.cwl"),
        get_data("tests/loop/single-var-loop-job.yml"),
    ]
    assert main(params) == 1


def test_default_value_loop() -> None:
    """Test a loop whose source has a default value."""
    stream = StringIO()
    params = [
        "--enable-ext",
        get_data("tests/loop/default-value-loop.cwl"),
        get_data("tests/loop/single-var-loop-job.yml"),
    ]
    main(params, stdout=stream)
    expected = {"o1": [8, 11, 14, 17, 20]}
    assert json.loads(stream.getvalue()) == expected
