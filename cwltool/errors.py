class WorkflowException(Exception):
    pass


class UnsupportedRequirement(WorkflowException):
    pass


class ArgumentException(Exception):
    """Mismatched command line arguments provided."""
