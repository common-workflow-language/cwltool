import json

from .util import get_data, get_main_output


def test_cwl_output_json_missing_field_v1_0() -> None:
    """Confirm that unknown outputs are propagated from cwl.output.json in CWL v1.0."""
    err_code, stdout, _ = get_main_output([get_data("tests/test-cwl-out-v1.0.cwl")])
    assert err_code == 0
    assert "foo" in json.loads(stdout)


def test_cwl_output_json_missing_field_v1_1() -> None:
    """Confirm that unknown outputs are propagated from cwl.output.json in CWL v1.1."""
    err_code, stdout, _ = get_main_output([get_data("tests/test-cwl-out-v1.1.cwl")])
    assert err_code == 0
    assert "foo" in json.loads(stdout)


def test_cwl_output_json_missing_field_v1_2() -> None:
    """Confirm that unknown outputs are propagated from cwl.output.json in CWL v1.2."""
    err_code, stdout, _ = get_main_output([get_data("tests/test-cwl-out-v1.2.cwl")])
    assert err_code == 0
    assert "foo" in json.loads(stdout)


def test_cwl_output_json_missing_field_v1_3() -> None:
    """Confirm that unknown outputs are propagated from cwl.output.json in CWL v1.3."""
    err_code, stdout, stderr = get_main_output(
        ["--enable-dev", get_data("tests/test-cwl-out-v1.3.cwl")]
    )
    assert err_code == 0
    assert "foo" not in json.loads(stdout)
    assert "Discarded undeclared output named 'foo' from" in stderr
