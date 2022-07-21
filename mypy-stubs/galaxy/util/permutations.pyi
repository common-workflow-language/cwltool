from _typeshed import Incomplete
from galaxy.exceptions import MessageException as MessageException
from galaxy.util.bunch import Bunch as Bunch

input_classification: Incomplete

class InputMatchedException(MessageException): ...

def expand_multi_inputs(inputs, classifier, key_filter: Incomplete | None = ...): ...
