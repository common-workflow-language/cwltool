import pytest

from cwltool import sandboxjs
from cwltool.utils import onWindows

from .util import get_data, get_windows_safe_factory, windows_needs_docker


node_versions = [
    (b'v0.8.26\n', False),
    (b'v0.10.25\n', False),

    (b'v0.10.26\n', True),
    (b'v4.4.2\n', True),
    (b'v7.7.3\n', True)
]

@pytest.mark.parametrize('version,supported', node_versions)
def test_node_version(version, supported, mocker):
    mocked_subprocess = mocker.patch("cwltool.sandboxjs.subprocess")
    mocked_subprocess.check_output = mocker.Mock(return_value=version)

    assert sandboxjs.check_js_threshold_version('node') == supported

@windows_needs_docker
def test_value_from_two_concatenated_expressions():
    factory = get_windows_safe_factory()
    echo = factory.make(get_data("tests/wf/vf-concat.cwl"))
    file = {"class": "File",
            "location": get_data("tests/wf/whale.txt")}

    assert echo(file1=file) == {u"out": u"a string\n"}

@pytest.mark.skipif(onWindows(), reason="Caching processes for windows is not supported.")
def test_caches_js_processes(mocker):
    sandboxjs.exec_js_process("7", context="{}")

    mocked_new_js_proc = mocker.patch("cwltool.sandboxjs.new_js_proc")
    sandboxjs.exec_js_process("7", context="{}")

    mocked_new_js_proc.assert_not_called()
