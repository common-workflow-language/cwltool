import pytest
import os
from .util import get_data
from cwltool.main import main

def test_missing_enable_ext():
    # Requires --enable-ext and --enable-dev
    if "CWLTOOL_OPTIONS" in os.environ:
        del os.environ["CWLTOOL_OPTIONS"]
    assert main([get_data('tests/wf/generator/zing.cwl'),
                 "--zing", "zipper"]) == 1

    assert main(["--enable-ext", "--enable-dev",
                 get_data('tests/wf/generator/zing.cwl'),
                 "--zing", "zipper"]) == 0

    try:
        os.environ["CWLTOOL_OPTIONS"] = "--enable-ext --enable-dev"
        assert main([get_data('tests/wf/generator/zing.cwl'),
                     "--zing", "zipper"]) == 0
    finally:
        del os.environ["CWLTOOL_OPTIONS"]
