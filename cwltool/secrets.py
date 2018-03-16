import uuid
import six
from typing import (List, Dict, Any, Text, MutableMapping)

class SecretStore(object):
    def __init__(self):
        # type: () -> None
        self.secrets = {}  # type: Dict[Text, Text]

    def add(self, value):
        # type: (Text) -> Text
        if not isinstance(value, six.string_types):
            raise Exception("Secret store only accepts strings")

        if value not in self.secrets:
            placeholder = "(secret-%s)" % Text(uuid.uuid4())
            self.secrets[placeholder] = value
            return placeholder
        else:
            return value

    def store(self, secrets, job):
        # type: (List[Text], MutableMapping[Text, Any]) -> None
        for j in job:
            if j in secrets:
                job[j] = self.add(job[j])

    def has_secret(self, value):
        # type: (Any) -> bool
        if isinstance(value, six.string_types):
            for k in self.secrets:
                if k in value:
                    return True
        elif isinstance(value, dict):
            for v in value.values():
                if self.has_secret(v):
                    return True
        elif isinstance(value, list):
            for v in value:
                if self.has_secret(v):
                    return True
        return False

    def retrieve(self, value):
        # type: (Any) -> Any
        if isinstance(value, six.string_types):
            for k,v in self.secrets.items():
                value = value.replace(k, v)
        elif isinstance(value, dict):
            return {k: self.retrieve(v) for k,v in value.items()}
        elif isinstance(value, list):
            return [self.retrieve(v) for k,v in enumerate(value)]
        return value
