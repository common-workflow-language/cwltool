from _typeshed import Incomplete

class UCSCLimitException(Exception): ...

class UCSCOutWrapper:
    other: Incomplete
    lookahead: Incomplete
    def __init__(self, other) -> None: ...
    def __iter__(self): ...
    def __next__(self): ...
    def next(self): ...
    def readline(self): ...
