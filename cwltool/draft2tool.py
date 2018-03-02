# Do wildcard import of command_line_tool
from .command_line_tool import *

_logger = logging.getLogger("cwltool")
_logger.warning("'draft2tool.py' has been renamed to 'command_line_tool.py'"
                "and will be removed in the future.")
