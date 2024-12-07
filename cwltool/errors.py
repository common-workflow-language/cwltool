"""Common errors.

WorkflowException and GraphTargetMissingException are aliased to
equivalent errors from cwl_utils.errors and re-exported by this module
to avoid breaking the interface for other code.

"""

# flake8: noqa: F401

from cwl_utils.errors import GraphTargetMissingException as GraphTargetMissingException
from cwl_utils.errors import WorkflowException as WorkflowException


class UnsupportedRequirement(WorkflowException):
    pass


class ArgumentException(Exception):
    """Mismatched command line arguments provided."""
