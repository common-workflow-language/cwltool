import pytest
import urllib.parse

from pathlib import Path
from typing import cast
from ruamel.yaml.comments import CommentedMap
from schema_salad.sourceline import cmap

from cwltool.main import main
from cwltool.command_line_tool import CommandLineTool
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.update import INTERNAL_VERSION
from cwltool.utils import CWLObjectType
from .util import needs_docker


script = """
#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool
inputs:
  - id: input
    type: File
    inputBinding:
      position: 0
  - id: output
    type: string
outputs:
  - id: output
    type: File
    outputBinding:
      glob: "$(inputs.output)"
stdout: "$(inputs.output)"
baseCommand: [cat]
"""


@needs_docker
def test_spaces_in_input_files(tmp_path: Path) -> None:
    script_name = tmp_path / "script"
    spaces = tmp_path / "test with spaces"
    spaces.touch()
    with script_name.open(mode="w") as script_file:
        script_file.write(script)

    params = [
        "--debug",
        "--outdir",
        str(tmp_path / "outdir"),
        str(script_name),
        "--input",
        str(spaces),
        "--output",
        "test.txt",
    ]
    assert main(params) == 1
    assert main(["--relax-path-checks"] + params) == 0


@needs_docker
@pytest.mark.parametrize(
    "filename", ["測試", "그래프", "график", "𒁃", "☕😍", "امتحان", "abc+DEFGZ.z_12345-"]
)
def test_unicode_in_input_files(tmp_path: Path, filename: str) -> None:
    script_name = tmp_path / "script"
    inputfile = tmp_path / filename
    inputfile.touch()
    with script_name.open(mode="w") as script_file:
        script_file.write(script)

    params = [
        "--debug",
        "--outdir",
        str(tmp_path / "outdir"),
        str(script_name),
        "--input",
        str(inputfile),
        "--output",
        "test.txt",
    ]
    assert main(params) == 0


@needs_docker
@pytest.mark.parametrize(
    "filename", ["測試", "그래프", "график", "𒁃", "☕😍", "امتحان", "abc+DEFGZ.z_12345-"]
)
def test_unicode_in_output_files(tmp_path: Path, filename: str) -> None:
    script_name = tmp_path / "script"
    inputfile = tmp_path / "test"
    inputfile.touch()
    with script_name.open(mode="w") as script_file:
        script_file.write(script)

    params = [
        "--debug",
        "--outdir",
        str(tmp_path / "outdir"),
        str(script_name),
        "--input",
        str(inputfile),
        "--output",
        filename,
    ]
    assert main(params) == 0


def test_clt_returns_specialchar_names(tmp_path: Path) -> None:
    """Confirm that special characters in filenames do not cause problems."""
    loading_context = LoadingContext(
        {
            "metadata": {
                "cwlVersion": INTERNAL_VERSION,
                "http://commonwl.org/cwltool#original_cwlVersion": INTERNAL_VERSION,
            }
        }
    )
    clt = CommandLineTool(
        cast(
            CommentedMap,
            cmap(
                {
                    "cwlVersion": INTERNAL_VERSION,
                    "class": "CommandLineTool",
                    "inputs": [],
                    "outputs": [],
                    "requirements": [],
                }
            ),
        ),
        loading_context,
    )

    # Reserved characters will be URL encoded during the creation of a file URI
    # Internal references to files are in URI form, and are therefore URL encoded
    # Final output files should not retain their URL encoded filenames
    rfc_3986_gen_delims = [":", "/", "?", "#", "[", "]", "@"]
    rfc_3986_sub_delims = ["!", "$", "&", "'", "(", ")", "*", "+", ",", ";", "="]
    unix_reserved = ["/", "\0"]
    reserved = [
        special_char
        for special_char in (rfc_3986_gen_delims + rfc_3986_sub_delims)
        if special_char not in unix_reserved
    ]

    # Mock an "output" file with the above special characters in its name
    special = "".join(reserved)
    output_schema = cast(
        CWLObjectType, {"type": "File", "outputBinding": {"glob": special}}
    )
    mock_output = tmp_path / special
    mock_output.touch()

    # Prepare minimal arguments for CommandLineTool.collect_output()
    builder = clt._init_job({}, RuntimeContext())
    builder.pathmapper = clt.make_path_mapper(
        builder.files, builder.stagedir, RuntimeContext(), True
    )
    fs_access = builder.make_fs_access(str(tmp_path))

    result = cast(
        CWLObjectType,
        clt.collect_output(output_schema, builder, str(tmp_path), fs_access),
    )

    assert result["class"] == "File"
    assert result["basename"] == special
    assert result["nameroot"] == special
    assert str(result["location"]).endswith(urllib.parse.quote(special))
