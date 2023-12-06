from typing import Optional

class Recipe:
    cmd: Optional[str]
    comments: list[str]
    entrypoint: Optional[str]
    environ: list[str]
    files: list[str]
    layer_files: dict[str, str]
    install: list[str]
    labels: list[str]
    ports: list[str]
    test: Optional[str]
    volumes: list[str]
    workdir: Optional[str]
    layer: int
    fromHeader: Optional[str]
    source: Optional[Recipe]
    def __init__(self, recipe: Optional[Recipe] = ..., layer: int = ...) -> None: ...
