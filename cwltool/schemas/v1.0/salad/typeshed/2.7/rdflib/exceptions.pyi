# Stubs for rdflib.exceptions (Python 2)
#
# NOTE: This dynamically typed stub was automatically generated by stubgen.

from typing import Any


class Error(Exception):
    msg = ...  # type: Any

    def __init__(self, msg=None): ...


class TypeCheckError(Error):
    type = ...  # type: Any
    node = ...  # type: Any

    def __init__(self, node): ...


class SubjectTypeError(TypeCheckError):
    msg = ...  # type: Any

    def __init__(self, node): ...


class PredicateTypeError(TypeCheckError):
    msg = ...  # type: Any

    def __init__(self, node): ...


class ObjectTypeError(TypeCheckError):
    msg = ...  # type: Any

    def __init__(self, node): ...


class ContextTypeError(TypeCheckError):
    msg = ...  # type: Any

    def __init__(self, node): ...


class ParserError(Error):
    msg = ...  # type: Any

    def __init__(self, msg): ...


class UniquenessError(Error):
    def __init__(self, values): ...
