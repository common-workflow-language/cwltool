# Stubs for requests.packages.urllib3 (Python 3.4)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

import logging


class NullHandler(logging.Handler):
    def emit(self, record): ...


def add_stderr_logger(level=...): ...


def disable_warnings(category=...): ...
