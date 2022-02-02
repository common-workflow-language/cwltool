class WorkflowException(Exception):
    pass


class UnsupportedRequirement(WorkflowException):
    pass


class ArgumentException(Exception):
    """Mismatched command line arguments provided."""


class GraphTargetMissingException(WorkflowException):
    """When a $graph is encountered and there is no target and no main/#main."""
