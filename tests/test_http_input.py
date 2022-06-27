import os
from pathlib import Path
from typing import List
from datetime import datetime

from cwltool.pathmapper import PathMapper
from cwltool.utils import CWLObjectType, downloadHttpFile


def test_http_path_mapping(tmp_path: Path) -> None:

    input_file_path = "https://raw.githubusercontent.com/common-workflow-language/cwltool/main/tests/2.fasta"
    # input_file_path = "https://ibi.vu.nl/downloads/multi-task-PPI/test_ppi.zip"
    base_file: List[CWLObjectType] = [
        {
            "class": "File",
            "location": "https://raw.githubusercontent.com/common-workflow-language/cwltool/main/tests/2.fasta",
            # "location": "https://ibi.vu.nl/downloads/multi-task-PPI/test_ppi.zip",
            "basename": "chr20.fa",
        }
    ]
    pathmap = PathMapper(base_file, os.getcwd(), str(tmp_path))._pathmap

    assert input_file_path in pathmap
    assert os.path.exists(pathmap[input_file_path].resolved)

    with open(pathmap[input_file_path].resolved) as file:
        contents = file.read()

    assert ">Sequence 561 BP; 135 A; 106 C; 98 G; 222 T; 0 other;" in contents

def test_modification_date(tmp_path: Path) -> None:
    input_file_path = "https://ibi.vu.nl/downloads/multi-task-PPI/test_ppi.zip" # replace this with another remote file
    base_file: List[CWLObjectType] = [
        {
            "class": "File",
            "location": "https://ibi.vu.nl/downloads/multi-task-PPI/test_ppi.zip",
            "basename": "test_ppi.zip",
        }
    ]
    
    date_now = datetime.now() # the current datetime
    
    pathmap = PathMapper(base_file, os.getcwd(), str(tmp_path))._pathmap
    
    assert input_file_path in pathmap
    assert os.path.exists(pathmap[input_file_path].resolved)

    last_modified = os.path.getmtime(pathmap[input_file_path].resolved)

    assert date_now.timestamp() > last_modified # remote file should have earlier last modification date
    