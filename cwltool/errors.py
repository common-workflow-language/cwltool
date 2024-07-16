from cwl_utils.errors import WorkflowException as WorkflowException
from cwl_utils.errors import GraphTargetMissingException as GraphTargetMissingException


class UnsupportedRequirement(WorkflowException):
    pass


class ArgumentException(Exception):
    """Mismatched command line arguments provided."""
