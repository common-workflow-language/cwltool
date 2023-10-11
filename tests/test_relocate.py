import json
import os
import shutil
import sys
from pathlib import Path

from cwltool.main import main

from .util import get_data, needs_docker

if sys.version_info[0] < 3:
    from StringIO import StringIO
else:
    from io import StringIO


@needs_docker
def test_for_910(tmp_path: Path) -> None:
    assert main(["--outdir", str(tmp_path), get_data("tests/wf/910.cwl")]) == 0
    assert main(["--outdir", str(tmp_path), get_data("tests/wf/910.cwl")]) == 0


@needs_docker
def test_for_conflict_file_names(tmp_path: Path) -> None:
    stream = StringIO()

    assert (
        main(
            ["--debug", "--outdir", str(tmp_path), get_data("tests/wf/conflict.cwl")],
            stdout=stream,
        )
        == 0
    )

    out = json.loads(stream.getvalue())
    assert out["b1"]["basename"] == out["b2"]["basename"]
    assert out["b1"]["location"] != out["b2"]["location"]
    assert Path(out["b1"]["path"]).exists()
    assert Path(out["b2"]["path"]).exists()


def test_for_conflict_file_names_nodocker(tmp_path: Path) -> None:
    stream = StringIO()

    assert (
        main(
            ["--debug", "--outdir", str(tmp_path), get_data("tests/wf/conflict.cwl")],
            stdout=stream,
        )
        == 0
    )

    out = json.loads(stream.getvalue())
    assert out["b1"]["basename"] == out["b2"]["basename"]
    assert out["b1"]["location"] != out["b2"]["location"]
    assert Path(out["b1"]["path"]).exists()
    assert Path(out["b2"]["path"]).exists()


def test_relocate_symlinks(tmp_path: Path) -> None:
    shutil.copy(get_data("tests/reloc/test.cwl"), tmp_path)
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir1" / "foo").touch()
    os.symlink(tmp_path / "dir1", tmp_path / "dir2")
    assert (
        main(
            [
                "--debug",
                "--outdir",
                str(tmp_path / "dir2"),
                str(tmp_path / "test.cwl"),
                "--inp",
                str(tmp_path / "dir2"),
            ]
        )
        == 0
    )
