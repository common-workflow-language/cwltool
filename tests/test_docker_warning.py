from typing import Any, cast

import pytest
from ruamel.yaml.comments import CommentedMap
from schema_salad.sourceline import cmap

from cwltool import command_line_tool
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.utils import onWindows, windows_default_container_id


@pytest.mark.skip(not onWindows(), reason="MS Windows only")  # type: ignore
def test_default_docker_warning(mocker: Any) -> None:
    """Check warning when default docker Container is used on Windows."""
    mocker.patch("cwltool.command_line_tool._logger")

    tool = command_line_tool.CommandLineTool(
        cast(CommentedMap, cmap({"inputs": [], "outputs": []})), LoadingContext()
    )
    tool.make_job_runner(
        RuntimeContext({"find_default_container": lambda x: "frolvlad/alpine-bash"})
    )

    command_line_tool._logger.warning.assert_called_with(  # type: ignore
        command_line_tool.DEFAULT_CONTAINER_MSG,
        windows_default_container_id,
        windows_default_container_id,
    )
