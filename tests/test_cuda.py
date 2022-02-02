import pytest

from cwltool.cuda import cuda_version_and_device_count
from cwltool.main import main

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
        "--singularity",
        get_data("tests/wf/nvidia-smi.cwl"),
    ]
    assert main(params) == 0
