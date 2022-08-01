import asyncio
from concurrent.futures import Executor
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Iterator,
    List,
    MutableMapping,
    Optional,
    Pattern,
    Set,
    Sized,
    Tuple,
    Union,
)

from black.mode import Mode as Mode
from black.mode import TargetVersion as TargetVersion

FileContent = str
Encoding = str
NewLine = str
FileMode = Mode

def format_str(src_contents: str, mode: Mode) -> FileContent: ...
