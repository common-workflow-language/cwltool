from collections.abc import Generator

from _typeshed import Incomplete

WHITESPACE_PATTERN: Incomplete
DESCRIPTION: str
DEFAULT_HOMEBREW_ROOT: Incomplete
NO_BREW_ERROR_MESSAGE: str
CANNOT_DETERMINE_TAP_ERROR_MESSAGE: str
VERBOSE: bool
RELAXED: bool
BREW_ARGS: Incomplete

class BrewContext:
    homebrew_prefix: Incomplete
    homebrew_cellar: Incomplete
    def __init__(self, args: Incomplete | None = ...) -> None: ...

def main() -> None: ...

# def execute(cmds, env: Incomplete | None = ...): ...
# def which(file): ...
