import os
from pathlib import Path
from typing import List
from datetime import datetime

from cwltool.pathmapper import PathMapper
from cwltool.utils import CWLObjectType

from pytest_httpserver import HTTPServer


def test_http_path_mapping(tmp_path: Path) -> None:

    input_file_path = "https://raw.githubusercontent.com/common-workflow-language/cwltool/main/tests/2.fasta"
    base_file: List[CWLObjectType] = [
        {
            "class": "File",
            "location": "https://raw.githubusercontent.com/common-workflow-language/cwltool/main/tests/2.fasta",
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

    # Initialize the server
    headers = {
        'Server': 'nginx',
        'Date': 'Mon, 27 Jun 2022 14:26:17 GMT', 
        'Content-Type': 'application/zip', 
        'Content-Length': '123906', 
        'Connection': 'keep-alive', 
        'Last-Modified': 'Tue, 14 Dec 2021 14:23:30 GMT', 
        'ETag': '"1e402-5d31beef49671"', 
        'Accept-Ranges': 'bytes', 
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    }
    """
    Headers of 'real' response:
    {'Server': 'nginx', 'Date': 'Mon, 27 Jun 2022 14:26:17 GMT', 'Content-Type': 'application/zip', 'Content-Length': '123906', 'Connection': 'keep-alive', 'Last-Modified': 'Tue, 14 Dec 2021 14:23:30 GMT', 'ETag': '"1e402-5d31beef49671"', 'Accept-Ranges': 'bytes', 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'}
    """
    basename = 'testfile.txt' # name of the remote file

    with HTTPServer() as httpserver:
        httpserver.expect_request(f"/{basename}").respond_with_data(response_data="Hello World", headers=headers)   
        location = httpserver.url_for(f"/{basename}")
    # input_file_path = "https://ibi.vu.nl/downloads/multi-task-PPI/test_ppi.zip"  # replace this with another remote file
    base_file: List[CWLObjectType] = [
        {
            "class": "File",
            "location": location,
            "basename": basename,
        }
    ]

    date_now = datetime.now()  # the current datetime

    pathmap = PathMapper(base_file, os.getcwd(), str(tmp_path))._pathmap

    # assert input_file_path in pathmap
    assert location in pathmap
    assert os.path.exists(pathmap[location].resolved)

    last_modified = os.path.getmtime(pathmap[location].resolved)

    assert (
        date_now.timestamp() > last_modified
    )  # remote file should have earlier last modification date
