from _typeshed import Incomplete
from galaxy.util import asbool as asbool

log: Incomplete

class BaseField:
    name: Incomplete
    label: Incomplete
    value: Incomplete
    disabled: Incomplete
    optional: Incomplete
    help: Incomplete
    def __init__(
        self,
        name,
        value: Incomplete | None = ...,
        label: Incomplete | None = ...,
        **kwds
    ) -> None: ...
    def to_dict(self): ...

class TextField(BaseField):
    def to_dict(self): ...

class PasswordField(BaseField):
    def to_dict(self): ...

class TextArea(BaseField):
    def to_dict(self): ...

class CheckboxField(BaseField):
    @staticmethod
    def is_checked(value): ...
    def to_dict(self): ...

class SelectField(BaseField):
    field_id: Incomplete
    multiple: Incomplete
    refresh_on_change: Incomplete
    selectlist: Incomplete
    options: Incomplete
    display: Incomplete
    def __init__(
        self,
        name,
        multiple: Incomplete | None = ...,
        display: Incomplete | None = ...,
        field_id: Incomplete | None = ...,
        value: Incomplete | None = ...,
        selectlist: Incomplete | None = ...,
        refresh_on_change: bool = ...,
        **kwds
    ) -> None: ...
    def add_option(self, text, value, selected: bool = ...) -> None: ...
    def to_dict(self): ...

class AddressField(BaseField):
    @staticmethod
    def fields(): ...
    user: Incomplete
    security: Incomplete
    def __init__(
        self,
        name,
        user: Incomplete | None = ...,
        value: Incomplete | None = ...,
        security: Incomplete | None = ...,
        **kwds
    ) -> None: ...
    def to_dict(self): ...

class WorkflowField(BaseField):
    user: Incomplete
    value: Incomplete
    security: Incomplete
    def __init__(
        self,
        name,
        user: Incomplete | None = ...,
        value: Incomplete | None = ...,
        security: Incomplete | None = ...,
        **kwds
    ) -> None: ...
    def to_dict(self): ...

class WorkflowMappingField(BaseField):
    user: Incomplete
    def __init__(
        self,
        name,
        user: Incomplete | None = ...,
        value: Incomplete | None = ...,
        **kwds
    ) -> None: ...

class HistoryField(BaseField):
    user: Incomplete
    value: Incomplete
    security: Incomplete
    def __init__(
        self,
        name,
        user: Incomplete | None = ...,
        value: Incomplete | None = ...,
        security: Incomplete | None = ...,
        **kwds
    ) -> None: ...
    def to_dict(self): ...

def get_suite(): ...
