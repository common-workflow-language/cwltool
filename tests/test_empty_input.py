from io import StringIO
from pathlib import Path

import pytest

from cwltool.main import main

from .util import get_data


def test_empty_input(tmp_path: Path) -> None:
    """Affirm that an empty input works."""
    empty_json = "{}"
    empty_input = StringIO(empty_json)

    params = [
        "--outdir",
        str(tmp_path),
        get_data("tests/wf/no-parameters-echo.cwl"),
        "-",
    ]

    try:
        assert main(params, stdin=empty_input) == 0
    except SystemExit as err:
        assert err.code == 0


def test_empty_input_file(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """An empty job order file gets a meaningful error message, not a blank one."""
    empty_input = tmp_path / "empty.yml"
    empty_input.write_text("")

    params = [
        "--outdir",
        str(tmp_path),
        get_data("tests/wf/no-parameters-echo.cwl"),
        str(empty_input),
    ]

    with pytest.raises(SystemExit) as err:
        main(params)
    assert err.value.code == 1
    assert "is empty" in caplog.text
