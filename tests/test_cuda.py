from unittest import mock
from unittest.mock import MagicMock

import pytest
from schema_salad.avro import schema

from cwltool.builder import Builder
from cwltool.command_line_tool import CommandLineTool
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.cuda import cuda_version_and_device_count
from cwltool.errors import WorkflowException
from cwltool.job import CommandLineJob
from cwltool.load_tool import load_tool
from cwltool.main import main
from cwltool.process import use_custom_schema
from cwltool.stdfsaccess import StdFsAccess
from cwltool.update import INTERNAL_VERSION
from cwltool.utils import CWLObjectType

from .util import get_data, needs_docker, needs_singularity_3_or_newer

cuda_version = cuda_version_and_device_count()


@needs_docker
@pytest.mark.skipif(cuda_version[0] == "", reason="nvidia-smi required for CUDA not detected")
def test_cuda_docker() -> None:
    params = [
        "--enable-ext",
        get_data("tests/wf/nvidia-smi-container.cwl"),
    ]
    assert main(params) == 0


@needs_singularity_3_or_newer
@pytest.mark.skipif(cuda_version[0] == "", reason="nvidia-smi required for CUDA not detected")
def test_cuda_singularity() -> None:
    params = [
        "--enable-ext",
        "--singularity",
        get_data("tests/wf/nvidia-smi-container.cwl"),
    ]
    assert main(params) == 0


@pytest.mark.skipif(cuda_version[0] == "", reason="nvidia-smi required for CUDA not detected")
def test_cuda_no_container() -> None:
    params = [
        "--enable-ext",
        get_data("tests/wf/nvidia-smi.cwl"),
    ]
    assert main(params) == 0


@pytest.mark.skipif(cuda_version[0] == "", reason="nvidia-smi required for CUDA not detected")
def test_cuda_cc_list() -> None:
    params = [
        "--enable-ext",
        get_data("tests/wf/nvidia-smi-cc.cwl"),
    ]
    assert main(params) == 0


def _makebuilder(cudaReq: CWLObjectType) -> Builder:
    return Builder(
        {},
        [],
        [],
        {},
        schema.Names(),
        [cudaReq],
        [],
        {"cudaDeviceCount": 1},
        None,
        None,
        StdFsAccess,
        StdFsAccess(""),
        None,
        0.1,
        False,
        False,
        False,
        "no_listing",
        "",
        "",
        "",
        INTERNAL_VERSION,
        "docker",
    )


@mock.patch("subprocess.check_output")
@mock.patch("os.makedirs")
def test_cuda_job_setup_check(makedirs: MagicMock, check_output: MagicMock) -> None:
    runtime_context = RuntimeContext({})

    cudaReq: CWLObjectType = {
        "class": "http://commonwl.org/cwltool#CUDARequirement",
        "cudaVersionMin": "1.0",
        "cudaComputeCapability": "1.0",
    }
    builder = _makebuilder(cudaReq)

    check_output.return_value = """
<nvidia>
<attached_gpus>1</attached_gpus>
<cuda_version>1.0</cuda_version>
</nvidia>
"""

    jb = CommandLineJob(builder, {}, CommandLineTool.make_path_mapper, [], [], "")
    jb._setup(runtime_context)


@mock.patch("subprocess.check_output")
@mock.patch("os.makedirs")
def test_cuda_job_setup_check_err(makedirs: MagicMock, check_output: MagicMock) -> None:
    runtime_context = RuntimeContext({})

    cudaReq: CWLObjectType = {
        "class": "http://commonwl.org/cwltool#CUDARequirement",
        "cudaVersionMin": "2.0",
        "cudaComputeCapability": "1.0",
    }
    builder = _makebuilder(cudaReq)

    check_output.return_value = """
<nvidia>
<attached_gpus>1</attached_gpus>
<cuda_version>1.0</cuda_version>
</nvidia>
"""
    jb = CommandLineJob(builder, {}, CommandLineTool.make_path_mapper, [], [], "")
    with pytest.raises(WorkflowException):
        jb._setup(runtime_context)


@mock.patch("subprocess.check_output")
@mock.patch("os.makedirs")
def test_cuda_job_setup_check_err_empty_attached_gpus(
    makedirs: MagicMock, check_output: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    runtime_context = RuntimeContext({})

    cudaReq: CWLObjectType = {
        "class": "http://commonwl.org/cwltool#CUDARequirement",
        "cudaVersionMin": "1.0",
        "cudaComputeCapability": "1.0",
    }
    builder = _makebuilder(cudaReq)

    check_output.return_value = """
<nvidia>
<attached_gpus></attached_gpus>
<cuda_version>1.0</cuda_version>
</nvidia>
"""

    jb = CommandLineJob(builder, {}, CommandLineTool.make_path_mapper, [], [], "")
    with pytest.raises(WorkflowException):
        jb._setup(runtime_context)
    assert (
        "Error checking CUDA version with nvidia-smi. Missing 'attached_gpus' or it is empty."
        in caplog.text
    )


@mock.patch("subprocess.check_output")
@mock.patch("os.makedirs")
def test_cuda_job_setup_check_err_empty_missing_attached_gpus(
    makedirs: MagicMock, check_output: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    runtime_context = RuntimeContext({})

    cudaReq: CWLObjectType = {
        "class": "http://commonwl.org/cwltool#CUDARequirement",
        "cudaVersionMin": "1.0",
        "cudaComputeCapability": "1.0",
    }
    builder = _makebuilder(cudaReq)

    check_output.return_value = """
<nvidia>
<cuda_version>1.0</cuda_version>
</nvidia>
"""

    jb = CommandLineJob(builder, {}, CommandLineTool.make_path_mapper, [], [], "")
    with pytest.raises(WorkflowException):
        jb._setup(runtime_context)
    assert (
        "Error checking CUDA version with nvidia-smi. Missing 'attached_gpus' or it is empty."
        in caplog.text
    )


@mock.patch("subprocess.check_output")
@mock.patch("os.makedirs")
def test_cuda_job_setup_check_err_empty_cuda_version(
    makedirs: MagicMock, check_output: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    runtime_context = RuntimeContext({})

    cudaReq: CWLObjectType = {
        "class": "http://commonwl.org/cwltool#CUDARequirement",
        "cudaVersionMin": "1.0",
        "cudaComputeCapability": "1.0",
    }
    builder = _makebuilder(cudaReq)

    check_output.return_value = """
<nvidia>
<attached_gpus>1</attached_gpus>
<cuda_version></cuda_version>
</nvidia>
"""

    jb = CommandLineJob(builder, {}, CommandLineTool.make_path_mapper, [], [], "")
    with pytest.raises(WorkflowException):
        jb._setup(runtime_context)
    assert (
        "Error checking CUDA version with nvidia-smi. Missing 'cuda_version' or it is empty."
        in caplog.text
    )


@mock.patch("subprocess.check_output")
@mock.patch("os.makedirs")
def test_cuda_job_setup_check_err_missing_cuda_version(
    makedirs: MagicMock, check_output: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    runtime_context = RuntimeContext({})

    cudaReq: CWLObjectType = {
        "class": "http://commonwl.org/cwltool#CUDARequirement",
        "cudaVersionMin": "1.0",
        "cudaComputeCapability": "1.0",
    }
    builder = _makebuilder(cudaReq)

    check_output.return_value = """
<nvidia>
<attached_gpus>1</attached_gpus>
</nvidia>
"""

    jb = CommandLineJob(builder, {}, CommandLineTool.make_path_mapper, [], [], "")
    with pytest.raises(WorkflowException):
        jb._setup(runtime_context)
    assert (
        "Error checking CUDA version with nvidia-smi. Missing 'cuda_version' or it is empty."
        in caplog.text
    )


@mock.patch("subprocess.check_output")
@mock.patch("os.makedirs")
def test_cuda_job_setup_check_err_wrong_type_cuda_version(
    makedirs: MagicMock, check_output: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    runtime_context = RuntimeContext({})

    cudaReq: CWLObjectType = {
        "class": "http://commonwl.org/cwltool#CUDARequirement",
        "cudaVersionMin": "1.0",
        "cudaComputeCapability": "1.0",
    }
    builder = _makebuilder(cudaReq)

    check_output.return_value = """
<nvidia>
<attached_gpus>1</attached_gpus>
<cuda_version><subelement /></cuda_version>
</nvidia>
"""

    jb = CommandLineJob(builder, {}, CommandLineTool.make_path_mapper, [], [], "")
    with pytest.raises(WorkflowException):
        jb._setup(runtime_context)
    assert (
        "Error checking CUDA version with nvidia-smi. "
        "Either 'attached_gpus' or 'cuda_version' was not a text node" in caplog.text
    )


def test_cuda_eval_resource_range() -> None:
    with open(get_data("cwltool/extensions-v1.1.yml")) as res:
        use_custom_schema("v1.2", "http://commonwl.org/cwltool", res.read())

    joborder = {}  # type: CWLObjectType
    loadingContext = LoadingContext({"do_update": True})
    runtime_context = RuntimeContext({})

    tool = load_tool(get_data("tests/wf/nvidia-smi-range.cwl"), loadingContext)
    builder = _makebuilder(tool.requirements[0])
    builder.job = joborder

    resources = tool.evalResources(builder, runtime_context)

    assert resources["cudaDeviceCount"] == 2


def test_cuda_eval_resource_max() -> None:
    with open(get_data("cwltool/extensions-v1.1.yml")) as res:
        use_custom_schema("v1.2", "http://commonwl.org/cwltool", res.read())

    joborder = {}  # type: CWLObjectType
    loadingContext = LoadingContext({"do_update": True})
    runtime_context = RuntimeContext({})

    tool = load_tool(get_data("tests/wf/nvidia-smi-max.cwl"), loadingContext)
    builder = _makebuilder(tool.requirements[0])
    builder.job = joborder

    resources = tool.evalResources(builder, runtime_context)

    assert resources["cudaDeviceCount"] == 4
