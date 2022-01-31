"""Tests --validation."""


from .util import get_data, get_main_output


def test_validate_graph_with_no_default() -> None:
    """Ensure that --validate works on $graph docs that lack a main/#main."""
    exit_code, stdout, stderr = get_main_output(
        ["--validate", get_data("tests/wf/packed_no_main.cwl")]
    )
    assert exit_code == 0
    assert "packed_no_main.cwl#echo is valid CWL" in stdout
    assert "packed_no_main.cwl#cat is valid CWL" in stdout
    assert "packed_no_main.cwl#collision is valid CWL" in stdout
    assert "tests/wf/packed_no_main.cwl is valid CWL" in stdout
