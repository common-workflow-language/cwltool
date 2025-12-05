"""Test singularity{,-ce} & apptainer versions."""

import pytest
from packaging.version import Version

import cwltool.singularity
from cwltool.singularity import (
    get_version,
    is_apptainer_1_or_newer,
    is_version_2_6,
    is_version_3_1_or_newer,
    is_version_3_4_or_newer,
    is_version_3_or_newer,
)


def reset_singularity_version_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the cache for testing."""
    monkeypatch.setattr(cwltool.singularity, "_SINGULARITY_VERSION", None)
    monkeypatch.setattr(cwltool.singularity, "_SINGULARITY_FLAVOR", "")


def dummy_check_output(monkeypatch: pytest.MonkeyPatch, name: str, version: str) -> None:
    monkeypatch.setattr(
        cwltool.singularity, "check_output", (lambda c, text: name + " version " + version)
    )


def test_get_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirm expected types of singularity.get_version()."""
    with monkeypatch.context() as m:
        dummy_check_output(m, "apptainer", "1.0.1")
        reset_singularity_version_cache(m)
        v = get_version()
        assert isinstance(v, tuple)
        assert isinstance(v[0], Version)
        assert isinstance(v[1], str)
        assert (
            cwltool.singularity._SINGULARITY_VERSION is not None
        )  # pylint: disable=protected-access
        assert len(cwltool.singularity._SINGULARITY_FLAVOR) > 0  # pylint: disable=protected-access
        v_cached = get_version()
        assert v == v_cached
        assert v[0] == Version("1.0.1")
        assert v[1] == "apptainer"

    with monkeypatch.context() as m:
        dummy_check_output(m, "singularity", "3.8.5")
        reset_singularity_version_cache(m)
        v = get_version()
        assert v[0] == Version("3.8.5")
        assert v[1] == "singularity"


def test_version_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirm logic in the various singularity version checks."""
    with monkeypatch.context() as m:
        dummy_check_output(m, "apptainer", "1.0.1")
        reset_singularity_version_cache(m)
        assert is_apptainer_1_or_newer()
        assert not is_version_2_6()
        assert is_version_3_or_newer()
        assert is_version_3_1_or_newer()
        assert is_version_3_4_or_newer()

    with monkeypatch.context() as m:
        dummy_check_output(m, "apptainer", "0.0.1")
        reset_singularity_version_cache(m)
        assert not is_apptainer_1_or_newer()
        assert not is_version_2_6()
        assert not is_version_3_or_newer()
        assert not is_version_3_1_or_newer()
        assert not is_version_3_4_or_newer()

    with monkeypatch.context() as m:
        dummy_check_output(m, "singularity", "0.0.1")
        reset_singularity_version_cache(m)
        assert not is_apptainer_1_or_newer()
        assert not is_version_2_6()
        assert not is_version_3_or_newer()
        assert not is_version_3_1_or_newer()
        assert not is_version_3_4_or_newer()

    with monkeypatch.context() as m:
        dummy_check_output(m, "singularity", "0.1")
        reset_singularity_version_cache(m)
        assert not is_apptainer_1_or_newer()
        assert not is_version_2_6()
        assert not is_version_3_or_newer()
        assert not is_version_3_1_or_newer()
        assert not is_version_3_4_or_newer()

    with monkeypatch.context() as m:
        dummy_check_output(m, "singularity", "2.6")
        reset_singularity_version_cache(m)
        assert not is_apptainer_1_or_newer()
        assert is_version_2_6()
        assert not is_version_3_or_newer()
        assert not is_version_3_1_or_newer()
        assert not is_version_3_4_or_newer()

    with monkeypatch.context() as m:
        dummy_check_output(m, "singularity", "3.0")
        reset_singularity_version_cache(m)
        assert not is_apptainer_1_or_newer()
        assert not is_version_2_6()
        assert is_version_3_or_newer()
        assert not is_version_3_1_or_newer()
        assert not is_version_3_4_or_newer()

    with monkeypatch.context() as m:
        dummy_check_output(m, "singularity", "3.1")
        reset_singularity_version_cache(m)
        assert not is_apptainer_1_or_newer()
        assert not is_version_2_6()
        assert is_version_3_or_newer()
        assert is_version_3_1_or_newer()
        assert not is_version_3_4_or_newer()

    with monkeypatch.context() as m:
        dummy_check_output(m, "singularity", "3.4")
        reset_singularity_version_cache(m)
        assert not is_apptainer_1_or_newer()
        assert not is_version_2_6()
        assert is_version_3_or_newer()
        assert is_version_3_1_or_newer()
        assert is_version_3_4_or_newer()

    with monkeypatch.context() as m:
        dummy_check_output(m, "singularity", "3.6.3")
        reset_singularity_version_cache(m)
        assert not is_apptainer_1_or_newer()
        assert not is_version_2_6()
        assert is_version_3_or_newer()
        assert is_version_3_1_or_newer()
        assert is_version_3_4_or_newer()
