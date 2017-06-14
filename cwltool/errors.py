from __future__ import unicode_literals
class WorkflowException(Exception):
    pass


class UnsupportedRequirement(WorkflowException):
    pass
