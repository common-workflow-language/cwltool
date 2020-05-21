import pytest

from cwltool import command_line_tool, loghandler
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.utils import onWindows, windows_default_container_id


def test_default_docker_warning(mocker):
    """Check warning when default docker Container is used on Windows."""
    mocker.patch("cwltool.command_line_tool._logger")
    mocker.patch("cwltool.command_line_tool.onWindows", return_value=True)

    tool = command_line_tool.CommandLineTool(
        {"inputs": [], "outputs": []}, LoadingContext()
    )
    tool.make_job_runner(
        RuntimeContext({"find_default_container": lambda x: "frolvlad/alpine-bash"})
    )

    command_line_tool._logger.warning.assert_called_with(
        command_line_tool.DEFAULT_CONTAINER_MSG,
        windows_default_container_id,
        windows_default_container_id,
    )
