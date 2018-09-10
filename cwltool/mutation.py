from __future__ import absolute_import

from collections import namedtuple
from typing import Any, Dict

from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .errors import WorkflowException


MutationState = namedtuple("MutationTracker", ["generation", "readers", "stepname"])

_generation = "http://commonwl.org/cwltool#generation"

class MutationManager(object):
    """Lock manager for checking correctness of in-place update of files.

    Used to validate that in-place file updates happen sequentially, and that a
    file which is registered for in-place update cannot be read or updated by
    any other steps.

    """

    def __init__(self):  # type: () -> None
        self.generations = {}  # type: Dict[Text, MutationState]

    def register_reader(self, stepname, obj):
        # type: (Text, Dict[Text, Any]) -> None
        loc = obj["location"]
        current = self.generations.get(loc, MutationState(0, [], ""))
        obj_generation = obj.get(_generation, 0)

        if obj_generation != current.generation:
            raise WorkflowException(
                "[job {}] wants to read {} from generation {} but current "
                "generation is {}(last updated by {})".format(
                    stepname, loc, obj_generation, current.generation, current.stepname))

        current.readers.append(stepname)
        self.generations[loc] = current

    def release_reader(self, stepname, obj):
        # type: (Text, Dict[Text, Any]) -> None
        loc = obj["location"]
        current = self.generations.get(loc, MutationState(0, [], ""))
        obj_generation = obj.get(_generation, 0)

        if obj_generation != current.generation:
            raise WorkflowException(
                "[job {}] wants to release reader on {} from generation {}"
                " but current generation is {} (last updated by {})".format(
                    stepname, loc, obj_generation, current.generation,
                    current.stepname))

        self.generations[loc].readers.remove(stepname)

    def register_mutation(self, stepname, obj):
        # type: (Text, Dict[Text, Any]) -> None
        loc = obj["location"]
        current = self.generations.get(loc, MutationState(0, [], ""))
        obj_generation = obj.get(_generation, 0)

        if len(current.readers) > 0:
            raise WorkflowException(
                "[job {}] wants to modify {} but has readers: {}".format(
                    stepname, loc, current.readers))

        if obj_generation != current.generation:
            raise WorkflowException(
                "[job {}] wants to modify {} from generation {} but current "
                "generation is {} (last updated by {})".format(
                    stepname, loc, obj_generation, current.generation, current.stepname))

        self.generations[loc] = MutationState(current.generation+1, current.readers, stepname)

    def set_generation(self, obj):  # type: (Dict) -> None
        loc = obj["location"]
        current = self.generations.get(loc, MutationState(0, [], ""))
        obj[_generation] = current.generation

    def unset_generation(self, obj):  # type: (Dict) -> None
        obj.pop(_generation, None)
