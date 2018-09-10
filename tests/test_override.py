import json

from six import StringIO

import pytest

from cwltool.main import main

from .util import get_data, needs_docker

override_parameters = [
    ([get_data('tests/override/echo.cwl'),
      get_data('tests/override/echo-job.yml')],
     {"out": "zing hello1\n"}
     ),
    (["--overrides",
      get_data('tests/override/ov.yml'),
      get_data('tests/override/echo.cwl'),
      get_data('tests/override/echo-job.yml')],
     {"out": "zing hello2\n"}
     ),
    ([get_data('tests/override/echo.cwl'),
      get_data('tests/override/echo-job-ov.yml')],
     {"out": "zing hello3\n"}
     ),
    ([get_data('tests/override/echo-job-ov2.yml')],
     {"out": "zing hello4\n"}
     ),
    (["--overrides",
      get_data('tests/override/ov.yml'),
      get_data('tests/override/echo-wf.cwl'),
      get_data('tests/override/echo-job.yml')],
     {"out": "zing hello2\n"}
     ),
    (["--overrides",
      get_data('tests/override/ov2.yml'),
      get_data('tests/override/echo-wf.cwl'),
      get_data('tests/override/echo-job.yml')],
     {"out": "zing hello5\n"}
     ),
    (["--overrides",
      get_data('tests/override/ov3.yml'),
      get_data('tests/override/echo-wf.cwl'),
      get_data('tests/override/echo-job.yml')],
     {"out": "zing hello6\n"}
     ),
]

@needs_docker
@pytest.mark.parametrize('parameters,result', override_parameters)
def test_overrides(parameters, result):
    sio = StringIO()

    assert main(parameters, stdout=sio) == 0
    assert json.loads(sio.getvalue()) == result
