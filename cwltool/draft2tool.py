# Do wildcard import of tool
from .cltool import *

_logger = logging.getLogger("cwltool")
_logger.warning("'draft2tool.py' has been renamed to 'tool.py'" 
	"and will be removed in the future.")
