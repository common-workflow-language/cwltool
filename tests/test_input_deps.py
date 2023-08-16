"""Tests for --print-inputs-deps."""

import json
import os
from io import StringIO
from pathlib import Path

from cwltool.main import main
from cwltool.process import CWL_IANA

from .util import get_data


def test_input_deps() -> None:
    """Basic test of --print-input-deps with a job input file."""
    stream = StringIO()

    main(
        [
            "--print-input-deps",
            get_data("tests/wf/count-lines1-wf.cwl"),
            get_data("tests/wf/wc-job.json"),
        ],
        stdout=stream,
    )

    expected = {
        "class": "File",
        "location": "wc-job.json",
        "format": CWL_IANA,
        "secondaryFiles": [
            {
                "class": "File",
                "location": "whale.txt",
                "basename": "whale.txt",
                "nameroot": "whale",
                "nameext": ".txt",
            }
        ],
    }
    assert json.loads(stream.getvalue()) == expected


def test_input_deps_cmdline_opts() -> None:
    """Test of --print-input-deps with command line provided inputs."""
    stream = StringIO()

    main(
        [
            "--print-input-deps",
            get_data("tests/wf/count-lines1-wf.cwl"),
            "--file1",
            get_data("tests/wf/whale.txt"),
        ],
        stdout=stream,
    )
    expected = {
        "class": "File",
        "location": "",
        "format": CWL_IANA,
        "secondaryFiles": [
            {
                "class": "File",
                "location": "whale.txt",
                "basename": "whale.txt",
                "nameroot": "whale",
                "nameext": ".txt",
            }
        ],
    }
    assert json.loads(stream.getvalue()) == expected


def test_input_deps_cmdline_opts_relative_deps_cwd() -> None:
    """Test of --print-input-deps with command line provided inputs and relative-deps."""
    stream = StringIO()

    data_path = get_data("tests/wf/whale.txt")
    main(
        [
            "--print-input-deps",
            "--relative-deps",
            "cwd",
            get_data("tests/wf/count-lines1-wf.cwl"),
            "--file1",
            data_path,
        ],
        stdout=stream,
    )

    goal = {
        "class": "File",
        "location": "",
        "format": CWL_IANA,
        "secondaryFiles": [
            {
                "class": "File",
                "location": str(Path(os.path.relpath(data_path, os.path.curdir))),
                "basename": "whale.txt",
                "nameroot": "whale",
                "nameext": ".txt",
            }
        ],
    }
    assert json.loads(stream.getvalue()) == goal


def test_input_deps_secondary_files() -> None:
    """Affirm that secondaryFiles are also represented."""
    stream = StringIO()

    main(
        [
            "--print-input-deps",
            get_data("tests/input_deps/docker-array-secondaryfiles.cwl"),
            get_data("tests/input_deps/docker-array-secondaryfiles-job.json"),
        ],
        stdout=stream,
    )

    goal = {
        "class": "File",
        "location": "docker-array-secondaryfiles-job.json",
        "format": CWL_IANA,
        "secondaryFiles": [
            {
                "class": "File",
                "location": "ref.fasta",
                "basename": "ref.fasta",
                "secondaryFiles": [
                    {
                        "class": "File",
                        "location": "ref.fasta.fai",
                        "basename": "ref.fasta.fai",
                        "nameroot": "ref.fasta",
                        "nameext": ".fai",
                    }
                ],
                "nameroot": "ref",
                "nameext": ".fasta",
            },
            {
                "class": "File",
                "location": "ref2.fasta",
                "basename": "ref2.fasta",
                "secondaryFiles": [
                    {
                        "class": "File",
                        "location": "ref2.fasta.fai",
                        "basename": "ref2.fasta.fai",
                        "nameroot": "ref2.fasta",
                        "nameext": ".fai",
                    }
                ],
                "nameroot": "ref2",
                "nameext": ".fasta",
            },
        ],
    }

    assert json.loads(stream.getvalue()) == goal
