"""Test for Requirements and Hints in cwltool."""
import json
from io import StringIO

from cwltool.main import main
from .util import get_data


def test_workflow_reqs_are_evaluated_earlier_default_args() -> None:
    """Test that a Workflow process will evaluate the requirements earlier.

    Uses the default input values.

    This means that workflow steps, such as Expression and Command Line Tools
    can both use resources without re-evaluating expressions. This is useful
    when you have an expression that, for instance, dynamically decides
    how many threads/cpus to use.

    Issue: https://github.com/common-workflow-language/cwltool/issues/1330
    """
    stream = StringIO()

    assert (
        main(
            [get_data("tests/wf/1330.cwl")],
            stdout=stream,
        )
        == 0
    )

    out = json.loads(stream.getvalue())
    assert out["out"] == "2\n"


def test_workflow_reqs_are_evaluated_earlier_provided_inputs() -> None:
    """Test that a Workflow process will evaluate the requirements earlier.

    Passes inputs via a job file.

    This means that workflow steps, such as Expression and Command Line Tools
    can both use resources without re-evaluating expressions. This is useful
    when you have an expression that, for instance, dynamically decides
    how many threads/cpus to use.

    Issue: https://github.com/common-workflow-language/cwltool/issues/1330
    """
    stream = StringIO()

    assert (
        main(
            [get_data("tests/wf/1330.cwl"), get_data("tests/wf/1330.json")],
            stdout=stream,
        )
        == 0
    )

    out = json.loads(stream.getvalue())
    assert out["out"] == "1\n"
