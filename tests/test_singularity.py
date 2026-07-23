"""Tests to find local Singularity image."""

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mypy_extensions import KwArg, VarArg

from cwltool.main import main
from cwltool.singularity import (
    _IMAGES,
    _IMAGES_LOCK,
    _inspect_singularity_sandbox_image,
    _normalize_sif_id,
)

from .util import (
    get_data,
    get_main_output,
    needs_singularity,
    needs_singularity_2_6,
    needs_singularity_3_or_newer,
    working_directory,
)


@pytest.fixture(autouse=True)
def clear_singularity_image_cache() -> None:
    with _IMAGES_LOCK:
        _IMAGES.clear()


def test_normalize_sif_id_resists_collision() -> None:
    """Test that tricky image names can't collide."""
    assert _normalize_sif_id("ubuntu:latest")[0] != _normalize_sif_id("ubuntu_latest")[0]
    assert (
        _normalize_sif_id("docker://user_name/repo")[0]
        != _normalize_sif_id("docker://user/name_repo")[0]
    )
    assert (
        _normalize_sif_id("http://something.com/something.sif")[0]
        != _normalize_sif_id("http:_something.com/something.sif")[0]
    )


def test_normalize_sif_id_implies_latest() -> None:
    """
    Test that image names that imply latest are equivalent to those that
    specify it.
    """
    assert _normalize_sif_id("ubuntu")[0] == _normalize_sif_id("ubuntu:latest")[0]
    assert (
        _normalize_sif_id("quay.io/adamnovak/hap.py")[0]
        == _normalize_sif_id("quay.io/adamnovak/hap.py:latest")[0]
    )


def test_normalize_sif_id_does_not_tag_protocols() -> None:
    """
    Test that if an image comes from a string with a protocol, no tag is added.
    """
    assert (
        _normalize_sif_id("docker://library/ubuntu")[0]
        != _normalize_sif_id("docker://library/ubuntu:latest")[0]
    )


def test_normalize_sif_id_matches_cwl_utils_tests() -> None:
    """
    Make sure that the particular values tested in cwl-utils get the same
    answers here as there.
    """

    assert _normalize_sif_id("some_name/repo:123")[0] == "some___name_s_repo:123.sif"
    assert _normalize_sif_id("some/name_repo:123")[0] == "some_s_name___repo:123.sif"


# We have to include the normal name here because if there aren't slashes or
# underscores and a tag is included we generate the same names for the same
# images under the new and old schemes.


def test_normalize_sif_id_names_match_old_cwltool() -> None:
    """
    Make sure alternate image names tried match those previously used by
    cwltool 3.2.20260720092025.
    """

    def get_names(string: str) -> list[str]:
        name, alternate_names = _normalize_sif_id(string)
        return [name] + alternate_names

    assert "debian:stable-slim.sif" in get_names("debian:stable-slim")
    assert "quay.io_user_image_latest.sif" in get_names("quay.io/user/image")


def test_normalize_sif_id_names_match_old_cwl_utils() -> None:
    """
    Make sure alternate image names tried match those previously used by
    cwl-utils 0.42
    """

    def get_names(string: str) -> list[str]:
        name, alternate_names = _normalize_sif_id(string)
        return [name] + alternate_names

    assert "debian_stable-slim.sif" in get_names("debian:stable-slim")
    assert "quay.io_user_image.sif" in get_names("quay.io/user/image")


@needs_singularity_2_6
def test_singularity_pullfolder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test singularity respects SINGULARITY_PULLFOLDER."""
    workdir = tmp_path / "working_dir_new"
    workdir.mkdir()
    with working_directory(workdir):
        pullfolder = tmp_path / "pullfolder"
        pullfolder.mkdir()
        with monkeypatch.context() as m:
            result_code, stdout, stderr = get_main_output(
                [
                    "--singularity",
                    get_data("tests/sing_pullfolder_test.cwl"),
                    "--message",
                    "hello",
                ],
                extra_env={"SINGULARITY_PULLFOLDER": str(pullfolder)},
                monkeypatch=m,
            )
            print(stdout)
            print(stderr)
            assert result_code == 0
            image = pullfolder / "debian.img"
            assert image.exists()


@needs_singularity
def test_singularity_workflow(tmp_path: Path) -> None:
    with working_directory(tmp_path):
        error_code, _, stderr = get_main_output(
            [
                "--singularity",
                "--default-container",
                "docker.io/debian:stable-slim",
                "--debug",
                get_data("tests/wf/hello-workflow.cwl"),
                "--usermessage",
                "hello",
            ]
        )
    assert "completed success" in stderr, stderr
    assert error_code == 0


def test_singularity_iwdr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    singularity_dir = tmp_path / "singularity"
    singularity_dir.mkdir()
    with monkeypatch.context() as m:
        m.setenv("CWL_SINGULARITY_CACHE", str(singularity_dir))
        result_code = main(
            [
                "--debug",
                "--singularity",
                "--default-container",
                "docker.io/debian:stable-slim",
                get_data("tests/wf/iwdr-entry.cwl"),
                "--message",
                "hello",
            ]
        )
    singularity_installed = bool(shutil.which("singularity"))
    if singularity_installed:
        assert result_code == 0
    else:
        assert result_code != 0


@needs_singularity
def test_singularity_incorrect_image_pull() -> None:
    result_code, _, stderr = get_main_output(
        [
            "--singularity",
            "--default-container",
            "non-existant-weird-image",
            get_data("tests/wf/hello-workflow.cwl"),
            "--usermessage",
            "hello",
        ]
    )
    assert result_code != 0


@needs_singularity
def test_singularity_local(tmp_path: Path) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    with working_directory(workdir):
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/sing_pullfolder_test.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code == 0


@needs_singularity_2_6
def test_singularity2_docker_image_id_in_tool(tmp_path: Path) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    with working_directory(workdir):
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/sing_pullfolder_test.cwl"),
                "--message",
                "hello",
            ]
        )
        result_code1, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/debian_image_id.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code1 == 0


@needs_singularity_3_or_newer
def test_singularity3_docker_image_id_in_tool(tmp_path: Path) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    with working_directory(workdir):
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/sing_pullfolder_test.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code == 0, stderr
        result_code1, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/debian_image_id2.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code1 == 0


@needs_singularity_3_or_newer
def test_singularity_dockerfile_no_name_no_cache(tmp_path: Path) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    with working_directory(workdir):
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/sing_dockerfile_test.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code == 0, stderr
    assert not (workdir / _normalize_sif_id("bea92b9b6910cbbd2ae602f5bb0f0f27")[0]).exists()


@needs_singularity_3_or_newer
def test_singularity_dockerfile_no_name_with_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    cachedir = tmp_path / "cache"
    cachedir.mkdir()
    with monkeypatch.context() as m:
        m.setenv("CWL_SINGULARITY_CACHE", str(cachedir))
        with working_directory(workdir):
            result_code, stdout, stderr = get_main_output(
                [
                    "--singularity",
                    get_data("tests/sing_dockerfile_test.cwl"),
                    "--message",
                    "hello",
                ]
            )
            assert result_code == 0, stderr
    assert not (workdir / _normalize_sif_id("bea92b9b6910cbbd2ae602f5bb0f0f27")[0]).exists()
    assert (cachedir / _normalize_sif_id("bea92b9b6910cbbd2ae602f5bb0f0f27")[0]).exists()


@needs_singularity_3_or_newer
def test_singularity_dockerfile_with_name_no_cache(tmp_path: Path) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    with working_directory(workdir):
        result_code, stdout, stderr = get_main_output(
            [
                "--singularity",
                get_data("tests/sing_dockerfile_named_test.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code == 0, stderr
    print(list(workdir.iterdir()))
    assert not (workdir / _normalize_sif_id("bea92b9b6910cbbd2ae602f5bb0f0f27")[0]).exists()
    assert not (workdir / _normalize_sif_id("customDebian")[0]).exists()


@needs_singularity_3_or_newer
def test_singularity_dockerfile_with_name_with_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    cachedir = tmp_path / "cache"
    cachedir.mkdir()
    with monkeypatch.context() as m:
        m.setenv("CWL_SINGULARITY_CACHE", str(cachedir))
        with working_directory(workdir):
            result_code, stdout, stderr = get_main_output(
                [
                    "--singularity",
                    get_data("tests/sing_dockerfile_named_test.cwl"),
                    "--message",
                    "hello",
                ]
            )
            print(list(workdir.iterdir()))
            print(list(cachedir.iterdir()))
            assert result_code == 0, stderr
    assert not (workdir / _normalize_sif_id("bea92b9b6910cbbd2ae602f5bb0f0f27")[0]).exists()
    assert not (cachedir / _normalize_sif_id("bea92b9b6910cbbd2ae602f5bb0f0f27")[0]).exists()
    assert not (workdir / _normalize_sif_id("customDebian")[0]).exists()
    assert (cachedir / _normalize_sif_id("customDebian")[0]).exists()


@needs_singularity
def test_singularity_local_sandbox_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    # build a sandbox image
    container_path = workdir / "container_repo"
    container_path.mkdir()
    cmd = [
        "singularity",
        "build",
        "--sandbox",
        str(container_path / "alpine"),
        "docker://alpine:latest",
    ]
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode == 0:
        # test that we can work in sub directories
        with working_directory(workdir):
            result_code, _, _ = get_main_output(
                [
                    "--singularity",
                    "--disable-pull",
                    get_data("tests/sing_local_sandbox_test.cwl"),
                    "--message",
                    "hello",
                ]
            )
            assert result_code == 0
            result_code, _, _ = get_main_output(
                [
                    "--singularity",
                    "--disable-pull",
                    get_data("tests/sing_local_sandbox_img_id_test.cwl"),
                    "--message",
                    "hello",
                ]
            )
            assert result_code == 0
        # test with --singularity-sandbox-path option:
        result_code, out, err = get_main_output(
            [
                "--singularity",
                "--disable-pull",
                "--singularity-sandbox-path",
                f"{workdir}",
                get_data("tests/sing_local_sandbox_test.cwl"),
                "--message",
                "hello",
            ]
        )
        assert result_code == 0

        # test with CWL_SINGULARITY_IMAGES env variable set:
        with monkeypatch.context() as m:
            m.setenv("CWL_SINGULARITY_IMAGES", str(workdir))
            result_code, _, _ = get_main_output(
                [
                    "--singularity",
                    "--disable-pull",
                    get_data("tests/sing_local_sandbox_test.cwl"),
                    "--message",
                    "hello",
                ]
            )
            assert result_code == 0
    else:
        pytest.skip(f"Failed to build the singularity image: {build.stderr}")


@needs_singularity
def test_singularity_inspect_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test inspect a real image works."""
    workdir = tmp_path / "working_dir"
    workdir.mkdir()
    repo_path = workdir / "container_repo"
    image_path = repo_path / "alpine"

    # test image exists
    repo_path.mkdir()
    cmd = [
        "singularity",
        "build",
        "--sandbox",
        str(image_path),
        "docker://alpine:latest",
    ]
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode == 0:
        # Verify the path is a correct container image
        res_inspect = _inspect_singularity_sandbox_image(str(image_path))
        assert res_inspect is True
    else:
        pytest.skip(f"singularity sandbox image build didn't worked: {build.stderr}")


class _DummyResult:  # noqa: B903
    def __init__(self, rc: int, out: str) -> None:
        self.returncode = rc
        self.stdout = out


def _make_run_result(
    returncode: int, stdout: str
) -> Callable[[VarArg(Any), KwArg(Any)], _DummyResult]:
    """Mock subprocess.run returning returncode and stdout."""

    def _runner(*args: Any, **kwargs: Any) -> _DummyResult:
        return _DummyResult(returncode, stdout)

    return _runner


def test_json_decode_error_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test json can't decode inspect result."""
    monkeypatch.setattr("cwltool.singularity.run", _make_run_result(0, "not-a-json"))

    def _raise_json_error(s: str) -> None:
        # construct and raise an actual JSONDecodeError
        raise json.JSONDecodeError("Expecting value", s, 0)

    monkeypatch.setattr("json.loads", _raise_json_error)

    assert _inspect_singularity_sandbox_image("/tmp/image") is False


def test_singularity_sandbox_image_not_exists() -> None:
    image_path = "/tmp/not_existing/image"
    res_inspect = _inspect_singularity_sandbox_image(image_path)
    assert res_inspect is False


def test_singularity_sandbox_not_an_image(tmp_path: Path) -> None:
    image_path = tmp_path / "image"
    image_path.mkdir()
    res_inspect = _inspect_singularity_sandbox_image(str(image_path))
    assert res_inspect is False


def test_inspect_image_wrong_sb_call(monkeypatch: pytest.MonkeyPatch) -> None:

    def mock_failed_subprocess(*args: Any, **kwargs: Any) -> None:
        raise subprocess.CalledProcessError(returncode=1, cmd=args[0])

    monkeypatch.setattr("cwltool.singularity.run", mock_failed_subprocess)
    res_inspect = _inspect_singularity_sandbox_image("/tmp/container_repo/alpine")
    assert res_inspect is False
