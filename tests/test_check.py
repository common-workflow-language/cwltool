from __future__ import absolute_import
import unittest

import cwltool.expression as expr
import cwltool.factory
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
import pytest
from cwltool.main import main
from cwltool.utils import onWindows

from .util import get_data


class TestCheck(unittest.TestCase):
    @pytest.mark.skipif(onWindows(),
                        reason="Instance of Cwltool is used, On windows that invoke a default docker Container")
    def test_output_checking(self):
        self.assertEquals(main([get_data('tests/wf/badout1.cwl')]), 1)
        self.assertEquals(main([get_data('tests/wf/badout2.cwl')]), 1)
        self.assertEquals(main([get_data('tests/wf/badout3.cwl')]), 1)
