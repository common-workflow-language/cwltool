import json
import sys
from pathlib import Path

from cwltool.main import main

from .util import get_data, needs_docker

if sys.version_info[0] < 3:
    from StringIO import StringIO
else:
    from io import StringIO


@needs_docker
def test_for_910() -> None:
    assert main([get_data("tests/wf/910.cwl")]) == 0
    assert main([get_data("tests/wf/910.cwl")]) == 0


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
