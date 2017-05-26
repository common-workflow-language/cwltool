from __future__ import print_function

import glob
import logging
import os
import shutil
import subprocess
import tempfile
import time
import unittest

from funnel_test_util import SimpleServerTest, popen

class TestConformance(SimpleServerTest):
    def test_conformance(self):
        tmpdir = tempfile.mkdtemp(dir=self.tmpdir,
                                  prefix="v1.0_ctest_")
        cwl_testdir = os.path.join(self.testdir, "../../cwltool/schemas/v1.0")
        ctest_def = os.path.join(cwl_testdir, "conformance_test_v1.0.yaml")
        tool_entry = os.path.join(self.testdir,
                                  "../cwltool-tes")
        cmd = ["cwltest", "--test", ctest_def, "--basedir", tmpdir,
               "--tool", tool_entry, "-n", "1-71,73-87", "-j", "86"]
        process = popen(cmd,
                        cwd=os.path.join(self.testdir,
                                         "../../cwltool/schemas/v1.0")
        )
        process.wait()
        ctest_dirs = glob.glob(cwl_testdir + "[a-zA-Z0-9_]*")
        cleanup(self.tmpdir, ctest_dirs)
        assert process.returncode == 0


def cleanup(*args):
    for d in args:
        if isinstance(d, list):
            for sd in d:
                print("removing tempdir:", sd)
                shutil.rmtree(sd, True)
        else:
            print("removing tempdir:", d)
            shutil.rmtree(d, True)
