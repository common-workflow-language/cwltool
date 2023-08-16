"""Tests for various command line options."""

from cwltool.utils import versionstring

from .util import get_data, get_main_output, needs_docker


def test_version() -> None:
    """Test --version."""
    return_code, stdout, stderr = get_main_output(["--version"])
    assert return_code == 0
    assert versionstring() in stdout


def test_print_supported_versions() -> None:
    """Test --print-supported-versions."""
    return_code, stdout, stderr = get_main_output(["--print-supported-versions"])
    assert return_code == 0
    assert "v1.2" in stdout


def test_empty_cmdling() -> None:
    """Test empty command line."""
    return_code, stdout, stderr = get_main_output([])
    assert return_code == 1
    assert "CWL document required, no input file was provided" in stderr


def test_tool_help() -> None:
    """Test --tool-help."""
    return_code, stdout, stderr = get_main_output(["--tool-help", get_data("tests/echo.cwl")])
    assert return_code == 0
    assert "job_order   Job input json file" in stdout


def test_basic_pack() -> None:
    """Basic test of --pack. See test_pack.py for detailed testing."""
    return_code, stdout, stderr = get_main_output(["--pack", get_data("tests/wf/revsort.cwl")])
    assert return_code == 0
    assert "$graph" in stdout


@needs_docker
def test_basic_print_subgraph() -> None:
    """Basic test of --print-subgraph. See test_subgraph.py for detailed testing."""
    return_code, stdout, stderr = get_main_output(
        [
            "--print-subgraph",
            get_data("tests/subgraph/count-lines1-wf.cwl"),
        ]
    )
    assert return_code == 0
    assert "cwlVersion" in stdout


def test_error_graph_with_no_default() -> None:
    """Ensure a useful error is printed on $graph docs that lack a main/#main."""
    exit_code, stdout, stderr = get_main_output(
        ["--tool-help", get_data("tests/wf/packed_no_main.cwl")]
    )  # could be any command except --validate
    assert exit_code == 1
    assert (
        "Tool file contains graph of multiple objects, must specify one of #echo, #cat, #collision"
        in stderr
    )


def test_skip_schemas_external_step() -> None:
    """Test that --skip-schemas works even for bad schemas in external docs."""
    exit_code, stdout, stderr = get_main_output(
        [
            "--print-rdf",
            "--skip-schemas",
            get_data("tests/wf/revsort_step_bad_schema.cwl"),
        ]
    )
    assert exit_code == 0
    assert (
        "Repeat node-elements inside property elements: " "http://www.w3.org/1999/xhtmlmeta"
    ) not in stderr
    assert (
        "Could not load extension schema https://bad.example.com/missing.ttl: "
        "Error fetching https://bad.example.com/missing.ttl"
    ) not in stderr
