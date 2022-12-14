from os import PathLike
from typing import ContextManager

from ..cache import BaseCache as BaseCache
from ..controller import CacheController as CacheController

class _LockClass:
    path: str

_lock_class = ContextManager[_LockClass]

class FileCache(BaseCache):
    directory: str | PathLike[str]
    forever: bool
    filemode: str
    dirmode: str
    lock_class: _lock_class
    def __init__(
        self,
        directory: str | PathLike[str],
        forever: bool = ...,
        filemode: int = ...,
        dirmode: int = ...,
        use_dir_lock: bool | None = ...,
        lock_class: _lock_class | None = ...,
    ) -> None: ...
    @staticmethod
    def encode(x: str) -> str: ...
    def get(self, key: str) -> None | str: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...
