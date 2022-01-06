from pytest import LogCaptureFixture

from .util import get_main_output


def test_content_types(caplog: LogCaptureFixture) -> None:
    for _ in ("js_output.cwl", "js_output_workflow.cwl"):
        commands = [
            "https://raw.githubusercontent.com/common-workflow-language/common-workflow-language/main/v1.0/v1.0/test-cwl-out2.cwl",
            "https://github.com/common-workflow-language/common-workflow-language/blob/main/v1.0/v1.0/empty.json",
        ]
        error_code, _, stderr = get_main_output(commands)

        found = False
        for record in caplog.records:
            if (
                record.name == "salad"
                and "got content-type of 'text/html'" in record.message
            ):
                found = True
                break
        assert found
        assert error_code == 1, stderr
