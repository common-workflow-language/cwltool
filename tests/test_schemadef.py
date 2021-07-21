from cwltool.main import main
from .util import get_data


def test_schemadef() -> None:
    exit_code = main(["--validate", get_data("tests/wf/schemadef-bug-1473.cwl")])
    assert exit_code == 0
