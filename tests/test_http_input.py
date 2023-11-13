import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import pytest
from pytest_httpserver import HTTPServer

from cwltool.pathmapper import PathMapper
from cwltool.utils import CWLObjectType


def test_http_path_mapping(tmp_path: Path) -> None:
    input_file_path = (
        "https://raw.githubusercontent.com/common-workflow-language/cwltool/main/tests/2.fasta"
    )
    base_file: List[CWLObjectType] = [
        {
            "class": "File",
            "location": "https://raw.githubusercontent.com/common-workflow-language/"
            "cwltool/main/tests/2.fasta",
            "basename": "chr20.fa",
        }
    ]
    pathmap = PathMapper(base_file, os.getcwd(), str(tmp_path))._pathmap

    assert input_file_path in pathmap
    assert os.path.exists(pathmap[input_file_path].resolved)

    with open(pathmap[input_file_path].resolved) as file:
        contents = file.read()

    assert ">Sequence 561 BP; 135 A; 106 C; 98 G; 222 T; 0 other;" in contents


@pytest.mark.skipif(sys.version_info < (3, 7), reason="timesout on CI")
def test_modification_date(tmp_path: Path) -> None:
    """Local copies of remote files should preserve last modification date."""
    # Initialize the server
    headers = {
        "Server": "nginx",
        "Date": "Mon, 27 Jun 2022 14:26:17 GMT",
        "Content-Type": "application/zip",
        "Content-Length": "123906",
        "Connection": "keep-alive",
        "Last-Modified": "Tue, 14 Dec 2021 14:23:30 GMT",
        "ETag": '"1e402-5d31beef49671"',
        "Accept-Ranges": "bytes",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }

    remote_file_name = "testfile.txt"

    with HTTPServer() as httpserver:
        httpserver.expect_request(f"/{remote_file_name}").respond_with_data(
            response_data="Hello World", headers=headers
        )
        location = httpserver.url_for(f"/{remote_file_name}")

        base_file: List[CWLObjectType] = [
            {
                "class": "File",
                "location": location,
                "basename": remote_file_name,
            }
        ]

        date_now = datetime.now()

        pathmap = PathMapper(base_file, os.getcwd(), str(tmp_path))._pathmap

        assert location in pathmap
        assert os.path.exists(pathmap[location].resolved)

        last_modified = os.path.getmtime(pathmap[location].resolved)

        assert date_now.timestamp() > last_modified
