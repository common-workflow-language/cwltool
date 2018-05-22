from __future__ import absolute_import
import os
import shutil
import tempfile
import unittest
import pytest

import cwltool.expression as expr
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
from cwltool.main import main
from cwltool.utils import onWindows
from .util import get_data


@pytest.mark.skipif(onWindows(),
                    reason="Instance of Cwltool is used, On windows that invoke a default docker Container")
class TestListing(unittest.TestCase):
    def test_missing_enable_ext(self):
        # Require that --enable-ext is provided.
        self.assertEquals(main([get_data('tests/wf/listing_deep.cwl'), get_data('tests/listing-job.yml')]), 1)

    def test_listing_deep(self):
        # Should succeed.
        self.assertEquals(main(["--enable-ext", get_data('tests/wf/listing_deep.cwl'), get_data('tests/listing-job.yml')]), 0)

    def test_listing_shallow(self):
        # This fails on purpose, because it tries to access listing in a subdirectory the same way that listing_deep does,
        # but it shouldn't be expanded.
        self.assertEquals(main(["--enable-ext", get_data('tests/wf/listing_shallow.cwl'), get_data('tests/listing-job.yml')]), 1)

    def test_listing_none(self):
        # This fails on purpose, because it tries to access listing but it shouldn't be there.
        self.assertEquals(main(["--enable-ext", get_data('tests/wf/listing_none.cwl'), get_data('tests/listing-job.yml')]), 1)

    def test_listing_v1_0(self):
         # Default behavior in 1.0 is deep expansion.
         self.assertEquals(main([get_data('tests/wf/listing_v1_0.cwl'), get_data('tests/listing-job.yml')]), 0)

    # def test_listing_v1_1(self):
    #     # Default behavior in 1.1 will be no expansion
    #     self.assertEquals(main([get_data('tests/wf/listing_v1_1.cwl'), get_data('tests/listing-job.yml')]), 1)

@pytest.mark.skipif(onWindows(),
                    reason="InplaceUpdate uses symlinks,does not run on windows without admin privileges")
class TestInplaceUpdate(unittest.TestCase):

    def test_updateval(self):
        try:
            tmp = tempfile.mkdtemp()
            with open(os.path.join(tmp, "value"), "w") as f:
                f.write("1")
            out = tempfile.mkdtemp()
            self.assertEquals(main(["--outdir", out, get_data('tests/wf/updateval.cwl'), "-r", os.path.join(tmp, "value")]), 0)

            with open(os.path.join(tmp, "value"), "r") as f:
                self.assertEquals("1", f.read())
            with open(os.path.join(out, "value"), "r") as f:
                self.assertEquals("2", f.read())
        finally:
            shutil.rmtree(tmp)
            shutil.rmtree(out)

    def test_updateval_inplace(self):
        try:
            tmp = tempfile.mkdtemp()
            with open(os.path.join(tmp, "value"), "w") as f:
                f.write("1")
            out = tempfile.mkdtemp()
            self.assertEquals(main(["--enable-ext", "--leave-outputs", "--outdir", out, get_data('tests/wf/updateval_inplace.cwl'), "-r", os.path.join(tmp, "value")]), 0)

            with open(os.path.join(tmp, "value"), "r") as f:
                self.assertEquals("2", f.read())
            self.assertFalse(os.path.exists(os.path.join(out, "value")))
        finally:
            shutil.rmtree(tmp)
            shutil.rmtree(out)

    def test_write_write_conflict(self):
        try:
            tmp = tempfile.mkdtemp()
            with open(os.path.join(tmp, "value"), "w") as f:
                f.write("1")

            self.assertEquals(main(["--enable-ext", get_data('tests/wf/mut.cwl'), "-a", os.path.join(tmp, "value")]), 1)
            with open(os.path.join(tmp, "value"), "r") as f:
                self.assertEquals("2", f.read())
        finally:
            shutil.rmtree(tmp)

    def test_sequencing(self):
        try:
            tmp = tempfile.mkdtemp()
            with open(os.path.join(tmp, "value"), "w") as f:
                f.write("1")

            self.assertEquals(main(["--enable-ext", get_data('tests/wf/mut2.cwl'), "-a", os.path.join(tmp, "value")]), 0)
            with open(os.path.join(tmp, "value"), "r") as f:
                self.assertEquals("3", f.read())
        finally:
            shutil.rmtree(tmp)

    # def test_read_write_conflict(self):
    #     try:
    #         tmp = tempfile.mkdtemp()
    #         with open(os.path.join(tmp, "value"), "w") as f:
    #             f.write("1")

    #         self.assertEquals(main(["--enable-ext", get_data('tests/wf/mut3.cwl'), "-a", os.path.join(tmp, "value")]), 0)
    #     finally:
    #         shutil.rmtree(tmp)

    def test_updatedir(self):
        try:
            tmp = tempfile.mkdtemp()
            with open(os.path.join(tmp, "value"), "w") as f:
                f.write("1")
            out = tempfile.mkdtemp()

            self.assertFalse(os.path.exists(os.path.join(tmp, "blurb")))
            self.assertFalse(os.path.exists(os.path.join(out, "blurb")))

            self.assertEquals(main(["--outdir", out, get_data('tests/wf/updatedir.cwl'), "-r", tmp]), 0)

            self.assertFalse(os.path.exists(os.path.join(tmp, "blurb")))
            self.assertTrue(os.path.exists(os.path.join(out, "inp/blurb")))
        finally:
            shutil.rmtree(tmp)
            shutil.rmtree(out)

    def test_updatedir_inplace(self):
        try:
            tmp = tempfile.mkdtemp()
            with open(os.path.join(tmp, "value"), "w") as f:
                f.write("1")
            out = tempfile.mkdtemp()

            self.assertFalse(os.path.exists(os.path.join(tmp, "blurb")))
            self.assertFalse(os.path.exists(os.path.join(out, "blurb")))

            self.assertEquals(main(["--enable-ext", "--leave-outputs", "--outdir", out, get_data('tests/wf/updatedir_inplace.cwl'), "-r", tmp]), 0)

            self.assertTrue(os.path.exists(os.path.join(tmp, "blurb")))
            self.assertFalse(os.path.exists(os.path.join(out, "inp/blurb")))
        finally:
            shutil.rmtree(tmp)
            shutil.rmtree(out)
