import json
from io import StringIO
from typing import Dict, List

import pytest

from cwltool.main import main

from .util import get_data, needs_docker

override_parameters = [
    (
        [get_data("tests/override/echo.cwl"), get_data("tests/override/echo-job.yml")],
        {"out": "zing hello1\n"},
    ),
    (
        [
            "--overrides",
            get_data("tests/override/ov.yml"),
            get_data("tests/override/echo.cwl"),
            get_data("tests/override/echo-job.yml"),
        ],
        {"out": "zing hello2\n"},
    ),
    (
        [
            get_data("tests/override/echo.cwl"),
            get_data("tests/override/echo-job-ov.yml"),
        ],
        {"out": "zing hello3\n"},
    ),
    ([get_data("tests/override/echo-job-ov2.yml")], {"out": "zing hello4\n"}),
    (
        [
            "--overrides",
            get_data("tests/override/ov.yml"),
            get_data("tests/override/echo-wf.cwl"),
            get_data("tests/override/echo-job.yml"),
        ],
        {"out": "zing hello2\n"},
    ),
    (
        [
            "--overrides",
            get_data("tests/override/ov2.yml"),
            get_data("tests/override/echo-wf.cwl"),
            get_data("tests/override/echo-job.yml"),
        ],
        {"out": "zing hello5\n"},
    ),
    (
        [
            "--overrides",
            get_data("tests/override/ov3.yml"),
            get_data("tests/override/echo-wf.cwl"),
            get_data("tests/override/echo-job.yml"),
        ],
        {"out": "zing hello6\n"},
    ),
    (
        [
            get_data("tests/override/env-tool_v1.1.cwl"),
            get_data("tests/override/env-tool_cwl-requirement_override.yaml"),
        ],
        {"value": "hello test env"},
    ),
    (
        [
            "--enable-dev",
            get_data("tests/override/env-tool_cwl-requirement_override_default.yaml"),
        ],
        {"value": "hello test env"},
    ),
]


@needs_docker
@pytest.mark.parametrize("parameters,result", override_parameters)
def test_overrides(parameters: List[str], result: Dict[str, str]) -> None:
    sio = StringIO()

    assert main(parameters, stdout=sio) == 0
    assert json.loads(sio.getvalue()) == result


failing_override_parameters = [
    (
        [
            get_data("tests/override/env-tool.cwl"),
            get_data("tests/override/env-tool_cwl-requirement_override.yaml"),
        ],
        "`cwl:requirements` in the input object is not part of CWL v1.0. You can "
        "adjust to use `cwltool:overrides` instead; or you can set the cwlVersion to "
        "v1.1",
    ),
    (
        [
            get_data("tests/override/env-tool_v1.1.0-dev1.cwl"),
            get_data("tests/override/env-tool_cwl-requirement_override.yaml"),
        ],
        "Version 'v1.1.0-dev1' is a development or deprecated version.\n"
        " Update your document to a stable version (v1.0, v1.1, v1.2) or use --enable-dev to "
        "enable support for development and deprecated versions.",
    ),
    (
        [get_data("tests/override/env-tool_cwl-requirement_override_default_wrongver.yaml")],
        "`cwl:requirements` in the input object is not part of CWL v1.0. You can "
        "adjust to use `cwltool:overrides` instead; or you can set the cwlVersion to "
        "v1.1 or greater.",
    ),
    (
        [get_data("tests/override/env-tool_cwl-requirement_override_default.yaml")],
        "Version 'v1.1.0-dev1' is a development or deprecated version.\n"
        " Update your document to a stable version (v1.0, v1.1, v1.2) or use --enable-dev to "
        "enable support for development and deprecated versions.",
    ),
]


@needs_docker
@pytest.mark.parametrize("parameters,expected_error", failing_override_parameters)
def test_overrides_fails(parameters: List[str], expected_error: str) -> None:
    sio = StringIO()

    assert main(parameters, stderr=sio) == 1
    stderr = sio.getvalue()
    assert expected_error in stderr, stderr
