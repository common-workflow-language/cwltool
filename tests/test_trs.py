from typing import Any, Optional
from unittest import mock
from unittest.mock import MagicMock

from cwltool.loghandler import _logger
from cwltool.main import main

from .util import get_data


class MockResponse1:
    def __init__(
        self, json_data: Any, status_code: int, raise_for_status: Optional[bool] = None
    ) -> None:
        """Create a fake return object for requests.Session.head."""
        self.json_data = json_data
        self.status_code = status_code
        self.raise_for_status = mock.Mock()
        self.raise_for_status.side_effect = raise_for_status

    def json(self) -> Any:
        return self.json_data


def mocked_requests_head(*args: Any, **kwargs: Any) -> MockResponse1:
    return MockResponse1(None, 200)


class MockResponse2:
    def __init__(
        self, json_data: Any, status_code: int, raise_for_status: Optional[bool] = None
    ) -> None:
        """Create a fake return object for requests.Session.get."""
        self.json_data = json_data
        self.text = json_data
        self.status_code = status_code
        self.raise_for_status = mock.Mock()
        self.raise_for_status.side_effect = raise_for_status

    def json(self) -> Any:
        return self.json_data

    headers = {"content-type": "text/plain"}


def mocked_requests_get(*args: Any, **kwargs: Any) -> MockResponse2:
    if (
        args[0] == "https://dockstore.org/api/api/ga4gh/v2/tools/"
        "quay.io%2Fbriandoconnor%2Fdockstore-tool-md5sum/versions/1.0.4/CWL/files"
    ):
        return MockResponse2(
            [
                {"file_type": "CONTAINERFILE", "path": "Dockerfile"},
                {"file_type": "PRIMARY_DESCRIPTOR", "path": "Dockstore.cwl"},
                {"file_type": "TEST_FILE", "path": "test.json"},
            ],
            200,
        )
    elif (
        args[0] == "https://dockstore.org/api/api/ga4gh/v2/tools/"
        "quay.io%2Fbriandoconnor%2Fdockstore-tool-md5sum/versions/1.0.4/plain-CWL/descriptor/Dockstore.cwl"
    ):
        string = open(get_data("tests/trs/Dockstore.cwl")).read()
        return MockResponse2(string, 200)
    elif (
        args[0] == "https://dockstore.org/api/api/ga4gh/v2/tools/"
        "%23workflow%2Fgithub.com%2Fdockstore-testing%2Fmd5sum-checker/versions/develop/plain-CWL/descriptor/md5sum-tool.cwl"
    ):
        string = open(get_data("tests/trs/md5sum-tool.cwl")).read()
        return MockResponse2(string, 200)
    elif (
        args[0] == "https://dockstore.org/api/api/ga4gh/v2/tools/"
        "%23workflow%2Fgithub.com%2Fdockstore-testing%2Fmd5sum-checker/versions/develop/plain-CWL/descriptor/md5sum-workflow.cwl"
    ):
        string = open(get_data("tests/trs/md5sum-workflow.cwl")).read()
        return MockResponse2(string, 200)
    elif (
        args[0] == "https://dockstore.org/api/api/ga4gh/v2/tools/"
        "%23workflow%2Fgithub.com%2Fdockstore-testing%2Fmd5sum-checker/versions/develop/CWL/files"
    ):
        return MockResponse2(
            [
                {"file_type": "TEST_FILE", "path": "md5sum-input-cwl.json"},
                {"file_type": "SECONDARY_DESCRIPTOR", "path": "md5sum-tool.cwl"},
                {"file_type": "PRIMARY_DESCRIPTOR", "path": "md5sum-workflow.cwl"},
            ],
            200,
        )

    _logger.debug("A mocked call to TRS missed, target was %s", args[0])
    return MockResponse2(None, 404)


@mock.patch("requests.Session.head", side_effect=mocked_requests_head)
@mock.patch("requests.Session.get", side_effect=mocked_requests_get)
def test_tool_trs_template(mock_head: MagicMock, mock_get: MagicMock) -> None:
    params = [
        "--debug",
        "--make-template",
        r"quay.io/briandoconnor/dockstore-tool-md5sum:1.0.4",
    ]
    return_value = main(params)
    mock_head.assert_called()
    mock_get.assert_called()
    assert return_value == 0


@mock.patch("requests.Session.head", side_effect=mocked_requests_head)
@mock.patch("requests.Session.get", side_effect=mocked_requests_get)
def test_workflow_trs_template(mock_head: MagicMock, mock_get: MagicMock) -> None:
    params = [
        "--debug",
        "--make-template",
        r"#workflow/github.com/dockstore-testing/md5sum-checker:develop",
    ]
    return_value = main(params)
    mock_head.assert_called()
    mock_get.assert_called()
    assert return_value == 0
