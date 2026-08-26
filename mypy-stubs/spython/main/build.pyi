from collections.abc import Iterator
from typing import Literal, Optional, overload

from .base import Client

@overload
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
    stream: Literal[False] = ...,
    force: bool | None = ...,
    options: list[str] | None | None = ...,
    quiet: bool | None = ...,
    return_result: bool | None = ...,
    sudo_options: str | list[str] | None = ...,
    singularity_options: list[str] | None = ...,
) -> str | None: ...
@overload
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
    force: bool | None = ...,
    options: list[str] | None | None = ...,
    quiet: bool | None = ...,
    return_result: bool | None = ...,
    sudo_options: str | list[str] | None = ...,
    singularity_options: list[str] | None = ...,
) -> str | None: ...
@overload
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
    stream: Literal[True] = ...,
    force: bool | None = ...,
    options: list[str] | None | None = ...,
    quiet: bool | None = ...,
    return_result: bool | None = ...,
    sudo_options: str | list[str] | None = ...,
    singularity_options: list[str] | None = ...,
) -> tuple[str, Iterator[str]]: ...
@overload
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
) -> str | None | tuple[str, Iterator[str]]: ...
