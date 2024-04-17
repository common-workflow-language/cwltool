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


class WorkflowKillSwitch(Exception):
    """When processStatus != "success" and on-error=kill, raise this exception."""

    def __init__(self, job_id: str, rcode: int) -> None:
        """Record the job identifier and the error code."""
        self.job_id = job_id
        self.rcode = rcode

    def __str__(self) -> str:
        """Represent this exception as a string."""
        return f"[job {self.job_id}] activated kill switch with return code {self.rcode}"
