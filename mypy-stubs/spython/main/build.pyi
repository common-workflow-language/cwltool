from typing import Iterator, Optional

from .base import Client

def build(
    self: Client,
    recipe: Optional[str] = ...,
    image: Optional[str] = ...,
    isolated: Optional[bool] = ...,
    sandbox: Optional[bool] = ...,
    writable: Optional[bool] = ...,
    build_folder: Optional[str] = ...,
    robot_name: Optional[bool] = ...,
    ext: Optional[str] = ...,
    sudo: Optional[bool] = ...,
    stream: Optional[bool] = ...,
    force: Optional[bool] = ...,
    options: Optional[list[str]] | None = ...,
    quiet: Optional[bool] = ...,
    return_result: Optional[bool] = ...,
    sudo_options: Optional[str | list[str]] = ...,
    singularity_options: Optional[list[str]] = ...,
) -> tuple[str, Iterator[str]]: ...
