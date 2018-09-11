from .util import get_data, get_windows_safe_factory, windows_needs_docker

@windows_needs_docker
def test_newline_in_entry():
    """
    test that files in InitialWorkingDirectory are created with a newline character
    """
    factory = get_windows_safe_factory()
    echo = factory.make(get_data("tests/wf/iwdr-entry.cwl"))
    assert echo(message="hello") == {"out": "CONFIGVAR=hello\n"}
