from .util import get_data, get_main_output, needs_docker


@needs_docker
def test_docker_mem() -> None:
    error_code, stdout, stderr = get_main_output(
        [
            "--default-container=docker.io/debian:stable-slim",
            "--enable-ext",
            get_data("tests/wf/timelimit.cwl"),
            "--sleep_time",
            "10",
        ]
    )
    assert "Max memory used" in stderr, stderr
