from __future__ import absolute_import
import unittest

import cwltool.expression as expr
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
import pytest
import json
from cwltool.main import main
from cwltool.utils import onWindows
from six import StringIO

from .util import get_data


class TestOverride(unittest.TestCase):
    @pytest.mark.skipif(onWindows(),
                        reason="Instance of Cwltool is used, On windows that invoke a default docker Container")
    def test_overrides(self):
        sio = StringIO()

        self.assertEquals(main([get_data('tests/override/echo.cwl'),
                                get_data('tests/override/echo-job.yml')],
                               stdout=sio), 0)
        self.assertEquals({"out": "zing hello1\n"}, json.loads(sio.getvalue()))

        sio = StringIO()
        self.assertEquals(main(["--overrides", get_data('tests/override/ov.yml'),
                                get_data('tests/override/echo.cwl'),
                                get_data('tests/override/echo-job.yml')],
                               stdout=sio), 0)
        self.assertEquals({"out": "zing hello2\n"}, json.loads(sio.getvalue()))

        sio = StringIO()
        self.assertEquals(main([get_data('tests/override/echo.cwl'),
                                get_data('tests/override/echo-job-ov.yml')],
                               stdout=sio), 0)
        self.assertEquals({"out": "zing hello3\n"}, json.loads(sio.getvalue()))

        sio = StringIO()
        self.assertEquals(main([get_data('tests/override/echo-job-ov2.yml')],
                               stdout=sio), 0)
        self.assertEquals({"out": "zing hello4\n"}, json.loads(sio.getvalue()))


        sio = StringIO()
        self.assertEquals(main(["--overrides", get_data('tests/override/ov.yml'),
                                get_data('tests/override/echo-wf.cwl'),
                                get_data('tests/override/echo-job.yml')],
                               stdout=sio), 0)
        self.assertEquals({"out": "zing hello2\n"}, json.loads(sio.getvalue()))

        sio = StringIO()
        self.assertEquals(main(["--overrides", get_data('tests/override/ov2.yml'),
                                get_data('tests/override/echo-wf.cwl'),
                                get_data('tests/override/echo-job.yml')],
                               stdout=sio), 0)
        self.assertEquals({"out": "zing hello5\n"}, json.loads(sio.getvalue()))

        sio = StringIO()
        self.assertEquals(main(["--overrides", get_data('tests/override/ov3.yml'),
                                get_data('tests/override/echo-wf.cwl'),
                                get_data('tests/override/echo-job.yml')],
                               stdout=sio), 0)
        self.assertEquals({"out": "zing hello6\n"}, json.loads(sio.getvalue()))
