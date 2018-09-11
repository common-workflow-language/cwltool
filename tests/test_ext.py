from __future__ import absolute_import

import os
import shutil
import tempfile

import pytest

from cwltool.main import main

from .util import get_data, needs_docker, temp_dir, windows_needs_docker


@needs_docker
def test_missing_enable_ext():
    # Require that --enable-ext is provided.
    assert main([get_data('tests/wf/listing_deep.cwl'), get_data('tests/listing-job.yml')]) != 0

@needs_docker
def test_listing_deep():
    params = ["--enable-ext", get_data('tests/wf/listing_deep.cwl'),
              get_data('tests/listing-job.yml')]
    assert main(params) == 0

@needs_docker
def test_listing_shallow():
    # This fails on purpose, because it tries to access listing in a subdirectory
    # the same way that listing_deep does, but it shouldn't be expanded.
    params = ["--enable-ext", get_data('tests/wf/listing_shallow.cwl'),
              get_data('tests/listing-job.yml')]
    assert main(params) != 0

@needs_docker
def test_listing_none():
    # This fails on purpose, because it tries to access listing but it shouldn't be there.
    params = ["--enable-ext", get_data('tests/wf/listing_none.cwl'),
              get_data('tests/listing-job.yml')]
    assert main(params) != 0

@needs_docker
def test_listing_v1_0():
    # Default behavior in 1.0 is deep expansion.
    assert main([get_data('tests/wf/listing_v1_0.cwl'), get_data('tests/listing-job.yml')]) == 0

@pytest.mark.skip(reason="This is not the default behaviour yet")
@needs_docker
def test_listing_v1_1():
    # Default behavior in 1.1 will be no expansion
    assert main([get_data('tests/wf/listing_v1_1.cwl'), get_data('tests/listing-job.yml')]) != 0

@needs_docker
def test_double_overwrite():
    try:
        tmp = tempfile.mkdtemp()
        tmp_name = os.path.join(tmp, "value")

        before_value, expected_value = "1", "3"

        with open(tmp_name, "w") as f:
            f.write(before_value)

        assert main(["--enable-ext", get_data('tests/wf/mut2.cwl'), "-a", tmp_name]) == 0

        with open(tmp_name, "r") as f:
            actual_value = f.read()

        assert actual_value == expected_value
    finally:
        shutil.rmtree(tmp)

@needs_docker
def test_disable_file_overwrite_without_ext():
    try:
        tmp = tempfile.mkdtemp()
        out = tempfile.mkdtemp()

        tmp_name = os.path.join(tmp, "value")
        out_name = os.path.join(out, "value")

        before_value, expected_value = "1", "2"

        with open(tmp_name, "w") as f:
            f.write(before_value)

        assert main(["--outdir", out, get_data('tests/wf/updateval.cwl'), "-r", tmp_name]) == 0

        with open(tmp_name, "r") as f:
            tmp_value = f.read()
        with open(out_name, "r") as f:
            out_value = f.read()

        assert tmp_value == before_value
        assert out_value == expected_value
    finally:
        shutil.rmtree(tmp)
        shutil.rmtree(out)

@needs_docker
def test_disable_dir_overwrite_without_ext():
    try:
        tmp = tempfile.mkdtemp()
        out = tempfile.mkdtemp()

        assert main(["--outdir", out, get_data('tests/wf/updatedir.cwl'), "-r", tmp]) == 0

        assert not os.listdir(tmp)
        assert os.listdir(out)
    finally:
        shutil.rmtree(tmp)
        shutil.rmtree(out)

@needs_docker
def test_disable_file_creation_in_outdir_with_ext():
    try:
        tmp = tempfile.mkdtemp()
        out = tempfile.mkdtemp()

        tmp_name = os.path.join(tmp, "value")
        out_name = os.path.join(out, "value")

        before_value, expected_value = "1", "2"

        with open(tmp_name, "w") as f:
            f.write(before_value)

        params = ["--enable-ext", "--leave-outputs", "--outdir",
                  out, get_data('tests/wf/updateval_inplace.cwl'), "-r", tmp_name]
        assert main(params) == 0

        with open(tmp_name, "r") as f:
            tmp_value = f.read()

        assert tmp_value == expected_value
        assert not os.path.exists(out_name)
    finally:
        shutil.rmtree(tmp)
        shutil.rmtree(out)

@needs_docker
def test_disable_dir_creation_in_outdir_with_ext():
    try:
        tmp = tempfile.mkdtemp()
        out = tempfile.mkdtemp()
        params = ["--enable-ext", "--leave-outputs", "--outdir",
                  out, get_data('tests/wf/updatedir_inplace.cwl'), "-r", tmp]
        assert main(params) == 0

        assert os.listdir(tmp)
        assert not os.listdir(out)
    finally:
        shutil.rmtree(tmp)
        shutil.rmtree(out)

@needs_docker
def test_write_write_conflict():
    with temp_dir('tmp') as tmp:
        tmp = tempfile.mkdtemp()
        tmp_name = os.path.join(tmp, "value")

        before_value, expected_value = "1", "2"

        with open(tmp_name, "w") as f:
            f.write(before_value)

        assert main(["--enable-ext", get_data('tests/wf/mut.cwl'), "-a", tmp_name]) != 0

        with open(tmp_name, "r") as f:
            tmp_value = f.read()

        assert tmp_value == expected_value

@pytest.mark.skip(reason="This test is non-deterministic")
def test_read_write_conflict():
    with temp_dir('tmp') as tmp:
        tmp = tempfile.mkdtemp()
        tmp_name = os.path.join(tmp, "value")

        with open(tmp_name, "w") as f:
            f.write("1")

        assert main(["--enable-ext", get_data('tests/wf/mut3.cwl'), "-a", tmp_name]) != 0

@needs_docker
def test_require_prefix_networkaccess():
    assert main(["--enable-ext", get_data('tests/wf/networkaccess.cwl')]) == 0
    assert main([get_data('tests/wf/networkaccess.cwl')]) != 0
    assert main(["--enable-ext", get_data('tests/wf/networkaccess-fail.cwl')]) != 0

@needs_docker
def test_require_prefix_workreuse():
    assert main(["--enable-ext", get_data('tests/wf/workreuse.cwl')]) == 0
    assert main([get_data('tests/wf/workreuse.cwl')]) != 0
    assert main(["--enable-ext", get_data('tests/wf/workreuse-fail.cwl')]) != 0

@windows_needs_docker
def test_require_prefix_timelimit():
    assert main(["--enable-ext", get_data('tests/wf/timelimit.cwl')]) == 0
    assert main([get_data('tests/wf/timelimit.cwl')]) != 0
    assert main(["--enable-ext", get_data('tests/wf/timelimit-fail.cwl')]) != 0
