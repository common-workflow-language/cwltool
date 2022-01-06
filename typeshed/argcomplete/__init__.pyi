from typing import Any, Optional
import argparse
class CompletionFinder:
    always_complete_options: Any = ...
    exclude: Any = ...
    validator: Any = ...
    print_suppressed: Any = ...
    completing: bool = ...
    default_completer: Any = ...
    append_space: Any = ...
    def __init__(self, argument_parser: Optional[argparse.ArgumentParser] = ..., always_complete_options: bool = ..., exclude: Optional[Any] = ..., validator: Optional[Any] = ..., print_suppressed: bool = ..., default_completer: Any = ..., append_space: Optional[Any] = ...) -> None: ...
    def __call__(self, argument_parser: argparse.ArgumentParser, always_complete_options: bool = ..., exit_method: Any = ..., output_stream: Optional[Any] = ..., exclude: Optional[Any] = ..., validator: Optional[Any] = ..., print_suppressed: bool = ..., append_space: Optional[Any] = ..., default_completer: Any = ...) -> None: ...
    def collect_completions(self, active_parsers: Any, parsed_args: Any, cword_prefix: Any, debug: Any): ...
    def filter_completions(self, completions: Any): ...
    def quote_completions(self, completions: Any, cword_prequote: Any, last_wordbreak_pos: Any): ...
    def rl_complete(self, text: Any, state: Any): ...
    def get_display_completions(self): ...

class ExclusiveCompletionFinder(CompletionFinder): ...

autocomplete: CompletionFinder

