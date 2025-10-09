from collections.abc import Iterator
from typing import Optional

from .base import Client as _BaseClient
from .build import build as base_build

class _Client(_BaseClient):
    build = base_build

Client = _Client()
