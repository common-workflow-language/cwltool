from __future__ import absolute_import
import logging
import os
import sys
import typing
import threading

import six

from .utils import onWindows
__author__ = 'peter.amstutz@curoverse.com'

_logger = logging.getLogger("salad")
_logger.addHandler(logging.StreamHandler())
_logger.setLevel(logging.INFO)

__TMPDIR_LOCK = threading.Lock()

if six.PY3:

    if onWindows():
        # create '/tmp' folder if not present
        # required by autotranslate module
        # TODO: remove when https://github.com/PythonCharmers/python-future/issues/295
        # is fixed
        if not os.path.exists("/tmp"):
            with __TMPDIR_LOCK:
                try:
                    os.makedirs("/tmp")
                except OSError as exception:
                    _logger.error(u"Cannot create '\\tmp' folder in root needed for"
                                  "'cwltool' Python 3 installation.")
                    exit(1)
    with __TMPDIR_LOCK:
        from past import autotranslate  # type: ignore
        from past.translation import remove_hooks  # type: ignore
        autotranslate(['avro', 'avro.schema'])
        import avro
        import avro.schema  # pylint: disable=no-name-in-module,import-error
        remove_hooks()
