"""Shared logger for cwltool."""

import logging

import coloredlogs

_logger = logging.getLogger("cwltool")  # pylint: disable=invalid-name
defaultStreamHandler = logging.StreamHandler()  # pylint: disable=invalid-name
_logger.addHandler(defaultStreamHandler)
_logger.setLevel(logging.INFO)


def configure_logging(
    stderr_handler: logging.Handler,
    no_warnings: bool,
    quiet: bool,
    debug: bool,
    enable_color: bool,
    timestamps: bool,
    base_logger: logging.Logger = _logger,
) -> None:
    """Configure logging."""
    rdflib_logger = logging.getLogger("rdflib.term")
    rdflib_logger.addHandler(stderr_handler)
    rdflib_logger.setLevel(logging.ERROR)
    deps_logger = logging.getLogger("galaxy.tool_util.deps")
    deps_logger.addHandler(stderr_handler)
    ss_logger = logging.getLogger("salad")
    ss_logger.addHandler(stderr_handler)
    if no_warnings:
        stderr_handler.setLevel(logging.ERROR)
    if quiet:
        # Silence STDERR, not an eventual provenance log file
        stderr_handler.setLevel(logging.WARN)
    if debug:
        # Increase to debug for both stderr and provenance log file
        base_logger.setLevel(logging.DEBUG)
        stderr_handler.setLevel(logging.DEBUG)
        rdflib_logger.setLevel(logging.DEBUG)
        deps_logger.setLevel(logging.DEBUG)
    fmtclass = coloredlogs.ColoredFormatter if enable_color else logging.Formatter
    formatter = fmtclass("%(levelname)s %(message)s")
    if timestamps:
        formatter = fmtclass("[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    stderr_handler.setFormatter(formatter)
