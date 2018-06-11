from __future__ import absolute_import

import json
import unittest

from six import StringIO

from cwltool.main import main

from .util import get_data, needs_docker


class TestOverride(unittest.TestCase):
    @needs_docker
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
