import os
import sys

from cwltool.main import main
from cwltool.utils import subprocess

from .util import get_data


def test_rdf_print():
    assert main(['--print-rdf', get_data('tests/wf/hello_single_tool.cwl')]) == 0

def test_rdf_print_unicode():
    """Force ASCII encoding but load UTF file with --print-rdf."""
    try:
        lc_all = os.environ.get("LC_ALL", None)
        os.environ["LC_ALL"] = "C"

        params = [sys.executable,
                  "-m", "cwltool", '--print-rdf',
                  get_data('tests/utf_doc_example.cwl')]

        assert subprocess.check_call(params) == 0
    finally:
        if lc_all:
            os.environ["LC_ALL"] = lc_all
