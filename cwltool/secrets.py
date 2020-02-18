"""Minimal in memory storage of secrets."""
import uuid
from typing import Any, Dict, List, MutableMapping, MutableSequence


class SecretStore(object):
    """Minimal implementation of a secret storage."""

    def __init__(self):  # type: () -> None
        """Initialize the secret store."""
        self.secrets = {}  # type: Dict[str, str]

    def add(self, value):  # type: (str) -> str
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

    def store(self, secrets, job):
        # type: (List[str], MutableMapping[str, Any]) -> None
        """Sanitize the job object of any of the given secrets."""
        for j in job:
            if j in secrets:
                job[j] = self.add(job[j])

    def has_secret(self, value):  # type: (Any) -> bool
        """Test if the provided document has any of our secrets."""
        if isinstance(value, str):
            for k in self.secrets:
                if k in value:
                    return True
        elif isinstance(value, MutableMapping):
            for this_value in value.values():
                if self.has_secret(this_value):
                    return True
        elif isinstance(value, MutableSequence):
            for this_value in value:
                if self.has_secret(this_value):
                    return True
        return False

    def retrieve(self, value):  # type: (Any) -> Any
        """Replace placeholders with their corresponding secrets."""
        if isinstance(value, str):
            for key, this_value in self.secrets.items():
                value = value.replace(key, this_value)
        elif isinstance(value, MutableMapping):
            return {k: self.retrieve(v) for k, v in value.items()}
        elif isinstance(value, MutableSequence):
            return [self.retrieve(v) for k, v in enumerate(value)]
        return value
