import argparse
from typing import Any, Optional

class CompletionFinder:
    def __call__(
        self,
        argument_parser: argparse.ArgumentParser,
        always_complete_options: bool = ...,
        exit_method: Any = ...,
        output_stream: Optional[Any] = ...,
        exclude: Optional[Any] = ...,
        validator: Optional[Any] = ...,
        print_suppressed: bool = ...,
        append_space: Optional[Any] = ...,
        default_completer: Any = ...,
    ) -> None: ...

autocomplete: CompletionFinder
