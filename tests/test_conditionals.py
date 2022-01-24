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
