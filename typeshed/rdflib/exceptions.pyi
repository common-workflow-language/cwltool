from typing import Any

class Error(Exception):
    msg: Any
    def __init__(self, msg: Any | None = ...) -> None: ...

class TypeCheckError(Error):
    type: Any
    node: Any
    def __init__(self, node) -> None: ...

class SubjectTypeError(TypeCheckError):
    msg: Any
    def __init__(self, node) -> None: ...

class PredicateTypeError(TypeCheckError):
    msg: Any
    def __init__(self, node) -> None: ...

class ObjectTypeError(TypeCheckError):
    msg: Any
    def __init__(self, node) -> None: ...

class ContextTypeError(TypeCheckError):
    msg: Any
    def __init__(self, node) -> None: ...

class ParserError(Error):
    msg: Any
    def __init__(self, msg) -> None: ...

class UniquenessError(Error):
    def __init__(self, values) -> None: ...
