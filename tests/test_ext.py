import unittest

import cwltool.expression as expr
import cwltool.factory
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
from .util import get_data
from cwltool.main import main

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
