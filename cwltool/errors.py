# -*- coding: utf-8 -*-
from __future__ import unicode_literals
class WorkflowException(Exception):
    pass


class UnsupportedRequirement(WorkflowException):
    pass
