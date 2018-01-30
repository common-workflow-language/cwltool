# Do wildcard import of cltool
from .cltool import *

_logger = logging.getLogger("cwltool")
_logger.warning("'draft2tool.py' has been renamed to 'tool.py'" 
	"and will be removed in the future.")

