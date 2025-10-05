from typing import Optional

class Recipe:
    cmd: str | None
    comments: list[str]
    entrypoint: str | None
    environ: list[str]
    files: list[str]
    layer_files: dict[str, str]
    install: list[str]
    labels: list[str]
    ports: list[str]
    test: str | None
    volumes: list[str]
    workdir: str | None
    layer: int
    fromHeader: str | None
    source: Recipe | None
    def __init__(self, recipe: Recipe | None = ..., layer: int = ...) -> None: ...
