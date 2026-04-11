import subprocess
import sys

import pytest

from cwltool.main import main

from .util import get_data, get_main_output


def test_rdf_print() -> None:
    assert main(["--print-rdf", get_data("tests/wf/hello_single_tool.cwl")]) == 0


def test_rdf_print_inputs_and_defaults() -> None:
    error_code, stdout, stderr = get_main_output(
        ["--print-rdf", get_data("tests/wf/revsort.cwl"), get_data("tests/wf/revsort-job.json")]
    )
    assert error_code == 0, stderr
    assert "revsort.cwl#workflow_input> rdf:value " in stdout
    assert (
        'tests/wf/revsort.cwl#workflow_input> rdfs:comment "The input file to be processed."'
        not in stdout
    )


def test_rdf_print_unicode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force ASCII encoding but load UTF file with --print-rdf."""
    with monkeypatch.context() as m:
        m.setenv("LC_ALL", "C")
        params = [
            sys.executable,
            "-m",
            "cwltool",
            "--print-rdf",
            get_data("tests/utf_doc_example.cwl"),
        ]
        assert subprocess.check_call(params) == 0
