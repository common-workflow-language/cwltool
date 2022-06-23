"""Test singularity{,-ce} & apptainer versions."""
from subprocess import check_output  # nosec

import cwltool.singularity
from cwltool.singularity import (
    get_version,
    is_apptainer_1_or_newer,
    is_version_2_6,
    is_version_3_1_or_newer,
    is_version_3_4_or_newer,
    is_version_3_or_newer,
)


def reset_singularity_version_cache() -> None:
    """Reset the cache for testing."""
    cwltool.singularity._SINGULARITY_VERSION = None
    cwltool.singularity._SINGULARITY_FLAVOR = ""


def set_dummy_check_output(name: str, version: str) -> None:
    """Mock out subprocess.check_output."""
    cwltool.singularity.check_output = (  # type: ignore[attr-defined]
        lambda c, universal_newlines: name + " version " + version
    )


def restore_check_output() -> None:
    """Undo the mock of subprocess.check_output."""
    cwltool.singularity.check_output = check_output  # type: ignore[attr-defined]


def test_get_version() -> None:
    """Confirm expected types of singularity.get_version()."""
    set_dummy_check_output("apptainer", "1.0.1")
    reset_singularity_version_cache()
    v = get_version()
    assert isinstance(v, tuple)
    assert isinstance(v[0], list)
    assert isinstance(v[1], str)
    assert (
        cwltool.singularity._SINGULARITY_VERSION is not None
    )  # pylint: disable=protected-access
    assert (
        len(cwltool.singularity._SINGULARITY_FLAVOR) > 0
    )  # pylint: disable=protected-access
    v_cached = get_version()
    assert v == v_cached

    assert v[0][0] == 1
    assert v[0][1] == 0
    assert v[0][2] == 1
    assert v[1] == "apptainer"

    set_dummy_check_output("singularity", "3.8.5")
    reset_singularity_version_cache()
    v = get_version()

    assert v[0][0] == 3
    assert v[0][1] == 8
    assert v[0][2] == 5
    assert v[1] == "singularity"
    restore_check_output()


def test_version_checks() -> None:
    """Confirm logic in the various singularity version checks."""
    set_dummy_check_output("apptainer", "1.0.1")
    reset_singularity_version_cache()
    assert is_apptainer_1_or_newer()
    assert not is_version_2_6()
    assert is_version_3_or_newer()
    assert is_version_3_1_or_newer()
    assert is_version_3_4_or_newer()

    set_dummy_check_output("apptainer", "0.0.1")
    reset_singularity_version_cache()
    assert not is_apptainer_1_or_newer()
    assert not is_version_2_6()
    assert not is_version_3_or_newer()
    assert not is_version_3_1_or_newer()
    assert not is_version_3_4_or_newer()

    set_dummy_check_output("singularity", "0.0.1")
    reset_singularity_version_cache()
    assert not is_apptainer_1_or_newer()
    assert not is_version_2_6()
    assert not is_version_3_or_newer()
    assert not is_version_3_1_or_newer()
    assert not is_version_3_4_or_newer()

    set_dummy_check_output("singularity", "0.1")
    reset_singularity_version_cache()
    assert not is_apptainer_1_or_newer()
    assert not is_version_2_6()
    assert not is_version_3_or_newer()
    assert not is_version_3_1_or_newer()
    assert not is_version_3_4_or_newer()

    set_dummy_check_output("singularity", "2.6")
    reset_singularity_version_cache()
    assert not is_apptainer_1_or_newer()
    assert is_version_2_6()
    assert not is_version_3_or_newer()
    assert not is_version_3_1_or_newer()
    assert not is_version_3_4_or_newer()

    set_dummy_check_output("singularity", "3.0")
    reset_singularity_version_cache()
    assert not is_apptainer_1_or_newer()
    assert not is_version_2_6()
    assert is_version_3_or_newer()
    assert not is_version_3_1_or_newer()
    assert not is_version_3_4_or_newer()

    set_dummy_check_output("singularity", "3.1")
    reset_singularity_version_cache()
    assert not is_apptainer_1_or_newer()
    assert not is_version_2_6()
    assert is_version_3_or_newer()
    assert is_version_3_1_or_newer()
    assert not is_version_3_4_or_newer()

    set_dummy_check_output("singularity", "3.4")
    reset_singularity_version_cache()
    assert not is_apptainer_1_or_newer()
    assert not is_version_2_6()
    assert is_version_3_or_newer()
    assert is_version_3_1_or_newer()
    assert is_version_3_4_or_newer()

    set_dummy_check_output("singularity", "3.6.3")
    reset_singularity_version_cache()
    assert not is_apptainer_1_or_newer()
    assert not is_version_2_6()
    assert is_version_3_or_newer()
    assert is_version_3_1_or_newer()
    assert is_version_3_4_or_newer()
    restore_check_output()
