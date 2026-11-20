from cwltool.main import main
from tests.util import get_data


def test_cuda_requirement_v1_0() -> None:
    """Test that CUDARequirement objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/cuda-requirement_v1_0.cwl"),
    ]
    assert main(params) == 0


def test_cuda_requirement_v1_1() -> None:
    """Test that CUDARequirement objects are correctly loaded for CWL v1.1."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/cuda-requirement_v1_1.cwl"),
    ]
    assert main(params) == 0


def test_cuda_requirement_v1_2() -> None:
    """Test that CUDARequirement objects are correctly loaded for CWL v1.2."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/cuda-requirement_v1_2.cwl"),
    ]
    assert main(params) == 0


def test_load_listing_requirement_v1_0() -> None:
    """Test that LoadListingRequirement objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/load-listing-requirement_v1_0.cwl"),
    ]
    assert main(params) == 0


def test_loop_v1_2() -> None:
    """Test that Loop and LoopInput objects are correctly loaded for CWL v1.2."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/single-var-loop_v1_2.cwl"),
    ]
    assert main(params) == 0


def test_inplace_update_requirement_v1_0() -> None:
    """Test that InplaceUpdateRequirement objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/inplace-update-requirement_v1_0.cwl"),
    ]
    assert main(params) == 0


def test_mpi_requirement_v1_0() -> None:
    """Test that MPIRequirement objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/mpi-requirement_v1_0.cwl"),
    ]
    assert main(params) == 0


def test_mpi_requirement_v1_1() -> None:
    """Test that MPIRequirement objects are correctly loaded for CWL v1.1."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/mpi-requirement_v1_1.cwl"),
    ]
    assert main(params) == 0


def test_mpi_requirement_v1_2() -> None:
    """Test that MPIRequirement objects are correctly loaded for CWL v1.2."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/mpi-requirement_v1_2.cwl"),
    ]
    assert main(params) == 0


def test_network_access_v1_0() -> None:
    """Test that NetworkAccess objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/network-access_v1_0.cwl"),
    ]
    assert main(params) == 0


def test_process_generator_v1_0() -> None:
    """Test that ProcessGenerator objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/process-generator_v1_0.cwl"),
    ]
    assert main(params) == 0


def test_process_generator_v1_1() -> None:
    """Test that ProcessGenerator objects are correctly loaded for CWL v1.1."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/process-generator_v1_1.cwl"),
    ]
    assert main(params) == 0


def test_process_generator_v1_2() -> None:
    """Test that ProcessGenerator objects are correctly loaded for CWL v1.2."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/process-generator_v1_2.cwl"),
    ]
    assert main(params) == 0


def test_secrets_v1_0() -> None:
    """Test that Secrets objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/secrets_v1_0.cwl"),
    ]
    assert main(params) == 0


def test_secrets_v1_1() -> None:
    """Test that Secrets objects are correctly loaded for CWL v1.1."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/secrets_v1_1.cwl"),
    ]
    assert main(params) == 0


def test_secrets_v1_2() -> None:
    """Test that Secrets objects are correctly loaded for CWL v1.2."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/secrets_v1_2.cwl"),
    ]
    assert main(params) == 0


def test_shm_size_v1_0() -> None:
    """Test that ShmSize objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/shm-size_v1_0.cwl"),
    ]
    assert main(params) == 0


def test_shm_size_v1_1() -> None:
    """Test that ShmSize objects are correctly loaded for CWL v1.1."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/shm-size_v1_1.cwl"),
    ]
    assert main(params) == 0


def test_shm_size_v1_2() -> None:
    """Test that ShmSize objects are correctly loaded for CWL v1.2."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/shm-size_v1_2.cwl"),
    ]
    assert main(params) == 0


def test_time_limit_v1_0() -> None:
    """Test that TimeLimit objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/time-limit_v1_0.cwl"),
    ]
    assert main(params) == 0


def test_work_reuse_v1_0() -> None:
    """Test that WorkReuse objects are correctly loaded for CWL v1.0."""
    params = [
        "--validate",
        "--enable-ext",
        "--fast-parser",
        get_data("tests/extensions/work-reuse_v1_0.cwl"),
    ]
    assert main(params) == 0
