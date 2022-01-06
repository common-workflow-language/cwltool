from typing import Any
from xml.sax import xmlreader

class Parser:
    def __init__(self) -> None: ...
    def parse(self, source, sink) -> None: ...

class InputSource(xmlreader.InputSource):
    content_type: Any
    auto_close: bool
    def __init__(self, system_id: Any | None = ...) -> None: ...
    def close(self) -> None: ...

class StringInputSource(InputSource):
    def __init__(self, value, system_id: Any | None = ...) -> None: ...

class URLInputSource(InputSource):
    url: Any
    content_type: Any
    response_info: Any
    def __init__(
        self, system_id: Any | None = ..., format: Any | None = ...
    ) -> None: ...

class FileInputSource(InputSource):
    file: Any
    def __init__(self, file) -> None: ...
