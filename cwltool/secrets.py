"""Minimal in memory storage of secrets."""

import uuid
from typing import Dict, List, MutableMapping, MutableSequence, Optional, cast

from .utils import CWLObjectType, CWLOutputType


class SecretStore:
    """Minimal implementation of a secret storage."""

    def __init__(self) -> None:
        """Initialize the secret store."""
        self.secrets: Dict[str, str] = {}

    def add(self, value: Optional[CWLOutputType]) -> Optional[CWLOutputType]:
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

    def store(self, secrets: List[str], job: CWLObjectType) -> None:
        """Sanitize the job object of any of the given secrets."""
        for j in job:
            if j in secrets:
                job[j] = self.add(job[j])

    def has_secret(self, value: CWLOutputType) -> bool:
        """Test if the provided document has any of our secrets."""
        if isinstance(value, str):
            for k in self.secrets:
                if k in value:
                    return True
        elif isinstance(value, MutableMapping):
            for this_value in value.values():
                if self.has_secret(cast(CWLOutputType, this_value)):
                    return True
        elif isinstance(value, MutableSequence):
            for this_value in value:
                if self.has_secret(cast(CWLOutputType, this_value)):
                    return True
        return False

    def retrieve(self, value: CWLOutputType) -> CWLOutputType:
        """Replace placeholders with their corresponding secrets."""
        if isinstance(value, str):
            for key, this_value in self.secrets.items():
                value = value.replace(key, this_value)
            return value
        elif isinstance(value, MutableMapping):
            return {k: self.retrieve(cast(CWLOutputType, v)) for k, v in value.items()}
        elif isinstance(value, MutableSequence):
            return [self.retrieve(cast(CWLOutputType, v)) for v in value]
        return value
