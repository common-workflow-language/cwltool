class WorkflowException(Exception):
    pass


class UnsupportedRequirement(WorkflowException):
    pass


class ArgumentException(Exception):
    """Mismatched command line arguments provided."""


class GraphTargetMissingException(WorkflowException):
    """When a ``$graph`` is encountered and there is no target and no ``main``/``#main``."""


class WorkflowKillSwitch(Exception):
    """When processStatus != "success" and on-error=kill, raise this exception."""

    def __init__(self, job_id: str, rcode: int) -> None:
        """Record the job identifier and the error code."""
        self.job_id = job_id
        self.rcode = rcode

    def __str__(self) -> str:
        """Represent this exception as a string."""
        return f"[job {self.job_id}] activated kill switch with return code {self.rcode}"
