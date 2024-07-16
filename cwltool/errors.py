from cwl_utils.errors import WorkflowException, GraphTargetMissingException

class UnsupportedRequirement(WorkflowException):
    pass


class ArgumentException(Exception):
    """Mismatched command line arguments provided."""
