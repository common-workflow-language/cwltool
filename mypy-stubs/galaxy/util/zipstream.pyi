from .path import safe_walk as safe_walk
from _typeshed import Incomplete
from collections.abc import Generator

class ZipstreamWrapper:
    upstream_mod_zip: Incomplete
    archive_name: Incomplete
    archive: Incomplete
    files: Incomplete
    size: int
    def __init__(
        self,
        archive_name: Incomplete | None = ...,
        upstream_mod_zip: bool = ...,
        upstream_gzip: bool = ...,
    ) -> None: ...
    def response(self) -> Generator[Incomplete, None, None]: ...
    def get_headers(self): ...
    def add_path(self, path, archive_name) -> None: ...
    def write(self, path, archive_name: Incomplete | None = ...) -> None: ...
