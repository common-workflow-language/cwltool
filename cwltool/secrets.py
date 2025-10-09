"""Minimal in memory storage of secrets."""

import uuid
from collections.abc import MutableMapping, MutableSequence

from .utils import CWLObjectType, CWLOutputType


class SecretStore:
    """Minimal implementation of a secret storage."""

    def __init__(self) -> None:
        """Initialize the secret store."""
        self.secrets: dict[str, str] = {}

    def add(self, value: CWLOutputType | None) -> CWLOutputType | None:
        """
        Add the given value to the store.

        Returns a placeholder value to use until the real value is needed.
        """
        if not isinstance(value, str):
            raise Exception("Secret store only accepts strings")

        if value not in self.secrets:
            placeholder = "(secret-%s)" % str(uuid.uuid4())
            self.secrets[placeholder] = value
            return placeholder
        return value

    def store(self, secrets: list[str], job: CWLObjectType) -> None:
        """Sanitize the job object of any of the given secrets."""
        for j in job:
            if j in secrets:
                job[j] = self.add(job[j])

    def has_secret(self, value: CWLOutputType) -> bool:
        """Test if the provided document has any of our secrets."""
        match value:
            case str(val):
                for k in self.secrets:
                    if k in val:
                        return True
            case MutableMapping() as v_dict:
                for this_value in v_dict.values():
                    if self.has_secret(this_value):
                        return True
            case MutableSequence() as seq:
                for this_value in seq:
                    if self.has_secret(this_value):
                        return True
        return False

    def retrieve(self, value: CWLOutputType) -> CWLOutputType:
        """Replace placeholders with their corresponding secrets."""
        match value:
            case str(val):
                for key, this_value in self.secrets.items():
                    val = val.replace(key, this_value)
                return val
            case MutableMapping() as v_dict:
                return {k: self.retrieve(v) for k, v in v_dict.items()}
            case MutableSequence() as seq:
                return [self.retrieve(v) for v in seq]
        return value
