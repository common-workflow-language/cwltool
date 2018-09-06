from cwltool import command_line_tool
from cwltool.utils import windows_default_container_id
from cwltool.context import RuntimeContext


# Test to check warning when default docker Container is used on Windows
def test_default_docker_warning(mocker):
    mocker.patch("cwltool.command_line_tool.onWindows", return_value=True)
    mocker.patch("cwltool.command_line_tool._logger")

    class TestCommandLineTool(command_line_tool.CommandLineTool):
        def __init__(self, **kwargs):
            self.requirements = []
            self.hints = []

        def find_default_container(self, args, builder):
            return windows_default_container_id

    tool = TestCommandLineTool()
    tool.make_job_runner(RuntimeContext({
        "find_default_container": lambda x: "frolvlad/alpine-bash"}))

    command_line_tool._logger.warning.assert_called_with(
        command_line_tool.DEFAULT_CONTAINER_MSG,
        windows_default_container_id,
        windows_default_container_id)
