from collections.abc import Iterator
from typing import Optional

from .base import Client

def build(
    self: Client,
    recipe: str | None = ...,
    image: str | None = ...,
    isolated: bool | None = ...,
    sandbox: bool | None = ...,
    writable: bool | None = ...,
    build_folder: str | None = ...,
    robot_name: bool | None = ...,
    ext: str | None = ...,
    sudo: bool | None = ...,
    stream: bool | None = ...,
    force: bool | None = ...,
    options: list[str] | None | None = ...,
    quiet: bool | None = ...,
    return_result: bool | None = ...,
    sudo_options: str | list[str] | None = ...,
    singularity_options: list[str] | None = ...,
) -> tuple[str, Iterator[str]]: ...
