# Do wildcard import of command_line_tool
from .command_line_tool import *  # pylint: disable=redefined-builtin,unused-wildcard-import,wildcard-import
from .loghandler import _logger

_logger.warning("'draft2tool.py' has been renamed to 'command_line_tool.py'"
                "and will be removed in the future.")
