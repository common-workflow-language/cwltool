from __future__ import absolute_import
import unittest
from mock import mock
from cwltool.utils import windows_default_container_id
from cwltool.draft2tool import DEFAULT_CONTAINER_MSG, CommandLineTool


class TestDefaultDockerWarning(unittest.TestCase):

    # Test to check warning when default docker Container is used on Windows
    @mock.patch("cwltool.draft2tool.onWindows",return_value = True)
    @mock.patch("cwltool.draft2tool._logger")
    def test_default_docker_warning(self,mock_logger,mock_windows):

        class TestCommandLineTool(CommandLineTool):
            def __init__(self, **kwargs):
                self.requirements=[]
                self.hints=[]

            def find_default_container(args, builder):
                return windows_default_container_id

        TestObject = TestCommandLineTool()
        TestObject.makeJobRunner()
        mock_logger.warning.assert_called_with(DEFAULT_CONTAINER_MSG%(windows_default_container_id, windows_default_container_id))
