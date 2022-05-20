"""Tests related to CWL v1.2+ "when" expressions and conditional handling."""

import json
import re

from .util import get_data, get_main_output


def test_conditional_step_no_inputs() -> None:
    """Confirm fix for bug that populated `self` object for `when` expressions."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/conditional_step_no_inputs.cwl"),
        ]
    )
    result = json.loads(stdout)["required"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result is None


def test_conditional_scatter_missing_input() -> None:
    """Test that scattering a missing array skips execution."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/scatter_before_when.cwl"),
        ]
    )
    result = json.loads(stdout)["optional_echoed_messages"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result == []


def test_scatter_empty_array() -> None:
    """Test that scattering an empty array skips execution."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/scatter_before_when.cwl"),
            get_data("tests/wf/scatter_before_when-inp_empty.yaml"),
        ]
    )
    result = json.loads(stdout)["optional_echoed_messages"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result == []


def test_scatter_and_conditional() -> None:
    """Test scattering a partially empty array with a conditional."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/scatter_before_when.cwl"),
            get_data("tests/wf/scatter_before_when-inp.yaml"),
        ]
    )
    result = json.loads(stdout)["optional_echoed_messages"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result == ["We\n", "come\n", "in\n", "peace\n"]


def test_scatter_dotproduct_empty_arrays() -> None:
    """Test that dotproduct scattering empty arrays skips execution."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/scatter_before_when_dotproduct.cwl"),
        ]
    )
    result = json.loads(stdout)["optional_echoed_messages"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result == []


def test_scatter_dotproduct_and_conditional() -> None:
    """Test dotproduct scattering with partially empty arrays."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/scatter_before_when_dotproduct.cwl"),
            get_data("tests/wf/scatter_before_when_dotproduct-inp.yaml"),
        ]
    )
    result = json.loads(stdout)["optional_echoed_messages"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result == [
        "We Never\n",
        "Come Out\n",
        "In Anything But\n",
        "Peace -- The Aliens\n",
    ]


def test_scatter_nested_crossproduct_empty_arrays() -> None:
    """Test that nested_dotproduct scattering empty arrays skips execution."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/scatter_before_when-nested_crossproduct.cwl"),
        ]
    )
    result = json.loads(stdout)["optional_echoed_messages"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result == []


def test_scatter_nested_crossproduct_and_conditional() -> None:
    """Test nested_crossproduct scattering with partially empty arrays."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/scatter_before_when-nested_crossproduct.cwl"),
            get_data("tests/wf/scatter_before_when_dotproduct-inp.yaml"),
        ]
    )
    result = json.loads(stdout)["optional_echoed_messages"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result == [
        ["We Never\n", "We Out\n", "We Anything But\n", None, "We -- The Aliens\n"],
        [
            "Come Never\n",
            "Come Out\n",
            "Come Anything But\n",
            None,
            "Come -- The Aliens\n",
        ],
        ["In Never\n", "In Out\n", "In Anything But\n", None, "In -- The Aliens\n"],
        [None, None, None, None, None],
    ]


def test_scatter_flat_crossproduct_empty_arrays() -> None:
    """Test that flat_dotproduct scattering empty arrays skips execution."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/scatter_before_when-flat_crossproduct.cwl"),
        ]
    )
    result = json.loads(stdout)["optional_echoed_messages"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result == []


def test_scatter_flat_crossproduct_and_conditional() -> None:
    """Test flat_crossproduct scattering with partially empty arrays."""
    err_code, stdout, stderr = get_main_output(
        [
            get_data("tests/wf/scatter_before_when-flat_crossproduct.cwl"),
            get_data("tests/wf/scatter_before_when_dotproduct-inp.yaml"),
        ]
    )
    result = json.loads(stdout)["optional_echoed_messages"]
    stderr = re.sub(r"\s\s+", " ", stderr)
    assert err_code == 0, stderr
    assert result == [
        "We Never\n",
        "We Out\n",
        "We Anything But\n",
        "We -- The Aliens\n",
        "Come Never\n",
        "Come Out\n",
        "Come Anything But\n",
        "Come -- The Aliens\n",
        "In Never\n",
        "In Out\n",
        "In Anything But\n",
        "In -- The Aliens\n",
        "Peace Never\n",
        "Peace Out\n",
        "Peace Anything But\n",
        "Peace -- The Aliens\n",
    ]
