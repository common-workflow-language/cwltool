from __future__ import absolute_import

import mock

from cwltool.main import main


def mocked_requests_head(*args):

    class MockResponse:
        def __init__(self, json_data, status_code, raise_for_status=None):
            self.json_data = json_data
            self.status_code = status_code
            self.raise_for_status = mock.Mock()
            self.raise_for_status.side_effect = raise_for_status

        def json(self):
            return self.json_data

    return MockResponse(None, 200)


def mocked_requests_get(*args):

    class MockResponse:
        def __init__(self, json_data, status_code, raise_for_status=None):
            self.json_data = json_data
            self.text = json_data
            self.status_code = status_code
            self.raise_for_status = mock.Mock()
            self.raise_for_status.side_effect = raise_for_status

        def json(self):
            return self.json_data

    if args[0] == 'https://dockstore.org/api/api/ga4gh/v2/tools/quay.io%2Fbriandoconnor%2Fdockstore-tool-md5sum/versions/1.0.4/CWL/files':
        return MockResponse(
            [{"file_type": "CONTAINERFILE", "path": "Dockerfile"}, {"file_type": "PRIMARY_DESCRIPTOR", "path": "Dockstore.cwl"},
             {"file_type": "TEST_FILE", "path": "test.json"}], 200)
    elif args[0] == 'https://dockstore.org/api/api/ga4gh/v2/tools/quay.io%2Fbriandoconnor%2Fdockstore-tool-md5sum/versions/1.0.4/plain-CWL/descriptor/Dockstore.cwl':
        f = open("tests/trs/Dockstore.cwl", "r")
        string = f.read()
        return MockResponse(string, 200)
    elif args[0] == 'https://dockstore.org/api/api/ga4gh/v2/tools/%23workflow%2Fgithub.com%2Fdockstore-testing%2Fmd5sum-checker/versions/develop/plain-CWL/descriptor/md5sum-tool.cwl':
        f = open("tests/trs/md5sum-tool.cwl", "r")
        string = f.read()
        return MockResponse(string, 200)
    elif args[0] == 'https://dockstore.org/api/api/ga4gh/v2/tools/%23workflow%2Fgithub.com%2Fdockstore-testing%2Fmd5sum-checker/versions/develop/plain-CWL/descriptor/md5sum-workflow.cwl':
        f = open("tests/trs/md5sum-workflow.cwl", "r")
        string = f.read()
        return MockResponse(string, 200)
    elif args[
        0] == 'https://dockstore.org/api/api/ga4gh/v2/tools/%23workflow%2Fgithub.com%2Fdockstore-testing%2Fmd5sum-checker/versions/develop/CWL/files':
        return MockResponse(
            [{"file_type": "TEST_FILE", "path": "md5sum-input-cwl.json"}, {"file_type": "SECONDARY_DESCRIPTOR", "path": "md5sum-tool.cwl"},
             {"file_type": "PRIMARY_DESCRIPTOR", "path": "md5sum-workflow.cwl"}], 200)

    return MockResponse(None, 404)


@mock.patch('requests.Session.head', side_effect=mocked_requests_head)
@mock.patch('requests.Session.get', side_effect=mocked_requests_get)
def test_tool_trs_template(mock_head, mock_get):
    params = ["--make-template", r"quay.io/briandoconnor/dockstore-tool-md5sum:1.0.4"]
    return_value = main(params)
    mock_head.assert_called()
    mock_get.assert_called()
    assert return_value == 0


@mock.patch('requests.Session.head', side_effect=mocked_requests_head)
@mock.patch('requests.Session.get', side_effect=mocked_requests_get)
def test_workflow_trs_template(mock_head, mock_get):
    params = ["--make-template", r"#workflow/github.com/dockstore-testing/md5sum-checker:develop"]
    return_value = main(params)
    mock_head.assert_called()
    mock_get.assert_called()
    assert return_value == 0
