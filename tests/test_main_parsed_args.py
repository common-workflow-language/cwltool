import io
from pathlib import Path

from cwltool.argparser import arg_parser
from cwltool.main import main

from .util import get_data


def test_main_parsed_args(tmp_path: Path) -> None:
    """Affirm that main can be called with parsed args only."""
    stdout = io.StringIO()
    stderr = io.StringIO()

    unparsed_args = [get_data("tests/echo.cwl"), "--inp", "Hello"]
    parsed_args = arg_parser().parse_args(unparsed_args)

    try:
        assert main(args=parsed_args, stdout=stdout, stderr=stderr) == 0
    except SystemExit as err:
        assert err.code == 0


def test_main_parsed_args_provenance(tmp_path: Path) -> None:
    """Affirm that main can be called with parsed args only, requesting provenance."""
    stdout = io.StringIO()
    stderr = io.StringIO()

    prov_folder = tmp_path / "provenance"  # will be created if necessary

    unparsed_args = ["--provenance", str(prov_folder), get_data("tests/echo.cwl"), "--inp", "Hello"]
    parsed_args = arg_parser().parse_args(unparsed_args)

    try:
        assert main(args=parsed_args, stdout=stdout, stderr=stderr) == 0
    except SystemExit as err:
        assert err.code == 0

    manifest_file = prov_folder / "metadata" / "manifest.json"
    assert manifest_file.is_file(), f"Can't find RO-Crate manifest {manifest_file}"
