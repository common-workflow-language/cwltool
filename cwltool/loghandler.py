import logging

_logger = logging.getLogger("cwltool")
defaultStreamHandler = logging.StreamHandler()
_logger.addHandler(defaultStreamHandler)
_logger.setLevel(logging.INFO)
