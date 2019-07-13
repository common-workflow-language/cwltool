"""Reference implementation of the CWL standards."""
from __future__ import absolute_import
import warnings
import sys
__author__ = 'pamstutz@veritasgenetics.com'

class CWLToolDeprecationWarning(Warning):
    pass

# Hate this?
# set PYTHONWARNINGS=ignore:DEPRECATION::cwltool.__init__
if sys.version_info < (3, 0):
    warnings.warn("""
DEPRECATION: Python 2.7 will reach the end of its life on January 1st, 2020.
Please upgrade your Python as the Python 2.7 version of cwltool won't be
maintained after that date.
""",  category=CWLToolDeprecationWarning)
