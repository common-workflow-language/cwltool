from io import StringIO
from pathlib import Path

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
