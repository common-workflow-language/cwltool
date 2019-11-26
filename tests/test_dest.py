from __future__ import absolute_import

import os
import shutil
import tempfile
import sys
import re
from io import StringIO

import pytest

from cwltool.main import main
import cwltool.process


from .util import get_data, needs_docker, temp_dir, windows_needs_docker


@windows_needs_docker
def test_array_dest1():
    with temp_dir("out") as out_dir:
        assert main(["--enable-ext", "--outdir="+out_dir, get_data('tests/destination/array-dest1.cwl')]) == 0
        assert os.path.isfile(os.path.join(out_dir, "bar/foo1"))
        assert os.path.isfile(os.path.join(out_dir, "bar/foo2"))

@windows_needs_docker
def test_array_dest2():
    with temp_dir("out") as out_dir:
        assert main(["--enable-ext", "--outdir="+out_dir, get_data('tests/destination/array-dest2.cwl')]) == 0
        assert os.path.isfile(os.path.join(out_dir, "bar/foo1"))
        assert os.path.isfile(os.path.join(out_dir, "baz/foo2"))

@windows_needs_docker
def test_array_dest3():
    with temp_dir("out") as out_dir:
        assert main(["--enable-ext", "--outdir="+out_dir, get_data('tests/destination/array-dest3.cwl')]) == 0
        assert os.path.isfile(os.path.join(out_dir, "bar"))
        assert os.path.isfile(os.path.join(out_dir, "baz"))

@windows_needs_docker
def test_array_dest4():
    with temp_dir("out") as out_dir:
        assert main(["--enable-ext", "--outdir="+out_dir, get_data('tests/destination/array-dest4.cwl')]) == 0
        assert os.path.isfile(os.path.join(out_dir, "bar/foo1"))
        assert os.path.isfile(os.path.join(out_dir, "bar/baz"))

@windows_needs_docker
def test_dest_expr():
    with temp_dir("out") as out_dir:
        assert main(["--enable-ext", "--outdir="+out_dir, get_data('tests/destination/dest-expr.cwl')]) == 0
        assert os.path.isfile(os.path.join(out_dir, "bar/foo"))

@windows_needs_docker
def test_directory_dest1():
    with temp_dir("out") as out_dir:
        assert main(["--enable-ext", "--outdir="+out_dir, get_data('tests/destination/directory-dest1.cwl')]) == 0
        assert os.path.isfile(os.path.join(out_dir, "bar/foo"))

@windows_needs_docker
def test_directory_dest2():
    with temp_dir("out") as out_dir:
        assert main(["--enable-ext", "--outdir="+out_dir, get_data('tests/destination/directory-dest2.cwl')]) == 0
        assert os.path.isfile(os.path.join(out_dir, "bar/baz/foo"))

@windows_needs_docker
def test_file_rename():
    with temp_dir("out") as out_dir:
        assert main(["--enable-ext", "--outdir="+out_dir, get_data('tests/destination/file-rename.cwl')]) == 0
        assert os.path.isfile(os.path.join(out_dir, "bar"))
