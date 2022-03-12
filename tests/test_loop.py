"""Test the prototype loop extension."""

from cwltool.main import main
from .util import get_data


def test_validate_loop() -> None:
    """Affirm that the sample loop workflow validates with --enable-ext."""
    params = [
        "--enable-ext",
        "--validate",
        get_data("tests/loop.cwl"),
    ]
    assert main(params) == 0


def test_validate_loop_fail_no_ext() -> None:
    """Affirm that the sample loop workflow does not validate when --enable-ext is missing."""
    params = [
        "--validate",
        get_data("tests/loop.cwl"),
    ]
    assert main(params) == 1
