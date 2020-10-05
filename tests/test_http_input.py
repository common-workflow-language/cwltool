import os
import tempfile
from typing import List

from cwltool.pathmapper import PathMapper
from cwltool.utils import CWLObjectType


def test_http_path_mapping() -> None:

    input_file_path = "https://raw.githubusercontent.com/common-workflow-language/cwltool/main/tests/2.fasta"
    tempdir = tempfile.mkdtemp()
    base_file = [
        {
            "class": "File",
            "location": "https://raw.githubusercontent.com/common-workflow-language/cwltool/main/tests/2.fasta",
            "basename": "chr20.fa",
        }
    ]  # type: List[CWLObjectType]
    pathmap = PathMapper(base_file, os.getcwd(), tempdir)._pathmap

    assert input_file_path in pathmap
    assert os.path.exists(pathmap[input_file_path].resolved)

    with open(pathmap[input_file_path].resolved) as file:
        contents = file.read()

    assert ">Sequence 561 BP; 135 A; 106 C; 98 G; 222 T; 0 other;" in contents
