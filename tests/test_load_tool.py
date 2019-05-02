from cwltool.load_tool import load_tool
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.errors import WorkflowException
import pytest
from .util import (get_data, get_main_output,
                   get_windows_safe_factory,
                   needs_docker, working_directory,
                   needs_singularity, temp_dir,
                   windows_needs_docker)
from cwltool.resolver import Path, resolve_local
from .test_fetch import norm

@windows_needs_docker
def test_check_version():
    """Test that it is permitted to load without updating, but not
    execute.  Attempting to execute without updating to the internal
    version should raise an error.

    """

    joborder = {"inp": "abc"}
    loadingContext = LoadingContext({"do_update": True})
    tool = load_tool(get_data("tests/echo.cwl"), loadingContext)
    for j in tool.job(joborder, None, RuntimeContext()):
        pass

    loadingContext = LoadingContext({"do_update": False})
    tool = load_tool(get_data("tests/echo.cwl"), loadingContext)
    with pytest.raises(WorkflowException):
        for j in tool.job(joborder, None, RuntimeContext()):
            pass

def test_use_metadata():
    """Test that it will use the version from loadingContext.metadata if
    cwlVersion isn't present in the document.

    """

    loadingContext = LoadingContext({"do_update": False})
    tool = load_tool(get_data("tests/echo.cwl"), loadingContext)

    loadingContext = LoadingContext()
    loadingContext.metadata = tool.metadata
    tooldata = tool.tool.copy()
    del tooldata["cwlVersion"]
    tool2 = load_tool(tooldata, loadingContext)

def test_checklink_outputSource():
    """Test that outputSource is resolved correctly independent of value
    of do_validate.

    """

    outsrc = norm(Path(get_data("tests/wf/1st-workflow.cwl")).as_uri())+"#argument/classfile"

    loadingContext = LoadingContext({"do_validate": True})
    tool = load_tool(get_data("tests/wf/1st-workflow.cwl"), loadingContext)
    assert tool.tool["outputs"][0]["outputSource"] == outsrc

    loadingContext = LoadingContext({"do_validate": False})
    tool = load_tool(get_data("tests/wf/1st-workflow.cwl"), loadingContext)
    assert tool.tool["outputs"][0]["outputSource"] == outsrc
