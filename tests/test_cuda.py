from unittest.mock import MagicMock

import mock
import pytest
from schema_salad.avro import schema

from cwltool.builder import Builder
from cwltool.context import LoadingContext, RuntimeContext
from cwltool.cuda import cuda_version_and_device_count
from cwltool.errors import WorkflowException
from cwltool.job import CommandLineJob
from cwltool.load_tool import load_tool
from cwltool.main import main
from cwltool.pathmapper import PathMapper
from cwltool.process import use_custom_schema
from cwltool.stdfsaccess import StdFsAccess
from cwltool.update import INTERNAL_VERSION
from cwltool.utils import CWLObjectType

from .util import get_data, needs_docker, needs_singularity_3_or_newer

cuda_version = cuda_version_and_device_count()


@needs_docker
@pytest.mark.skipif(
    cuda_version[0] == "", reason="nvidia-smi required for CUDA not detected"
)
def test_cuda_docker() -> None:
    params = [
        "--enable-ext",
        get_data("tests/wf/nvidia-smi-container.cwl"),
    ]
    assert main(params) == 0


@needs_singularity_3_or_newer
@pytest.mark.skipif(
    cuda_version[0] == "", reason="nvidia-smi required for CUDA not detected"
)
def test_cuda_singularity() -> None:
    params = [
        "--enable-ext",
        "--singularity",
        get_data("tests/wf/nvidia-smi-container.cwl"),
    ]
    assert main(params) == 0


@pytest.mark.skipif(
    cuda_version[0] == "", reason="nvidia-smi required for CUDA not detected"
)
def test_cuda_no_container() -> None:
    params = [
        "--enable-ext",
        get_data("tests/wf/nvidia-smi.cwl"),
    ]
    assert main(params) == 0


@pytest.mark.skipif(
    cuda_version[0] == "", reason="nvidia-smi required for CUDA not detected"
)
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
        "",
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

    jb = CommandLineJob(builder, {}, PathMapper, [], [], "")
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
    jb = CommandLineJob(builder, {}, PathMapper, [], [], "")
    with pytest.raises(WorkflowException):
        jb._setup(runtime_context)


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
