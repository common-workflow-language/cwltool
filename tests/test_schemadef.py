"""Tests related SchemaDefRequirement."""

from cwltool.main import main

from .util import get_data


def test_schemadef() -> None:
    """Confirm bug 1473 is fixed by checking that the test case validates."""
    exit_code = main(["--validate", get_data("tests/wf/schemadef-bug-1473.cwl")])
    assert exit_code == 0
