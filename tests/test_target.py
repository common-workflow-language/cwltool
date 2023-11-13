from cwltool.main import main

from .util import get_data


def test_target() -> None:
    """Test --target option successful."""
    test_file = "tests/wf/scatter-wf4.cwl"
    exit_code = main(["--target", "out", get_data(test_file), "--inp1", "INP1", "--inp2", "INP2"])
    assert exit_code == 0


def test_wrong_target() -> None:
    """Test --target option when value is wrong."""
    test_file = "tests/wf/scatter-wf4.cwl"
    exit_code = main(
        [
            "--target",
            "dummy_target",
            get_data(test_file),
            "--inp1",
            "INP1",
            "--inp2",
            "INP2",
        ]
    )
    assert exit_code == 1


def test_target_packed() -> None:
    """Test --target option with packed workflow schema."""
    test_file = "tests/wf/scatter-wf4.json"
    exit_code = main(["--target", "out", get_data(test_file), "--inp1", "INP1", "--inp2", "INP2"])
    assert exit_code == 0
