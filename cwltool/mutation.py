from __future__ import absolute_import
from collections import namedtuple
from typing import Any, Callable, Dict, Generator, Iterable, List, Text, Union, cast

from .errors import WorkflowException

MutationState = namedtuple("MutationTracker", ["generation", "readers", "stepname"])

_generation = "http://commonwl.org/cwltool#generation"

class MutationManager(object):
    """Lock manager for checking correctness of in-place update of files.

    Used to validate that in-place file updates happen sequentially, and that a
    file which is registered for in-place update cannot be read or updated by
    any other steps.

    """

    def __init__(self):
        # type: () -> None
        self.generations = {}  # type: Dict[Text, MutationState]

    def register_reader(self, stepname, obj):
        # type: (Text, Dict[Text, Any]) -> None
        loc = obj["location"]
        current = self.generations.get(loc, MutationState(0, [], ""))
        obj_generation = obj.get(_generation, 0)

        if obj_generation != current.generation:
            raise WorkflowException("[job %s] wants to read %s from generation %i but current generation is %s (last updated by %s)" % (
                                    stepname, loc, obj_generation, current.generation, current.stepname))

        current.readers.append(stepname)
        self.generations[loc] = current

    def release_reader(self, stepname, obj):
        # type: (Text, Dict[Text, Any]) -> None
        loc = obj["location"]
        current = self.generations.get(loc, MutationState(0, [], ""))
        obj_generation = obj.get(_generation, 0)

        if obj_generation != current.generation:
            raise WorkflowException("[job %s] wants to release reader on %s from generation %i but current generation is %s (last updated by %s)" % (
                                    stepname, loc, obj_generation, current.generation, current.stepname))

        self.generations[loc].readers.remove(stepname)

    def register_mutation(self, stepname, obj):
        # type: (Text, Dict[Text, Any]) -> None
        loc = obj["location"]
        current = self.generations.get(loc, MutationState(0,[], ""))
        obj_generation = obj.get(_generation, 0)

        if len(current.readers) > 0:
            raise WorkflowException("[job %s] wants to modify %s but has readers: %s" % (
                stepname, loc, current.readers))

        if obj_generation != current.generation:
            raise WorkflowException("[job %s] wants to modify %s from generation %i but current generation is %s (last updated by %s)" % (
                                    stepname, loc, obj_generation, current.generation, current.stepname))

        self.generations[loc] = MutationState(current.generation+1, current.readers, stepname)

    def set_generation(self, obj):
        # type: (Dict) -> None
        loc = obj["location"]
        current = self.generations.get(loc, MutationState(0,[], ""))
        obj[_generation] = current.generation

    def unset_generation(self, obj):
        # type: (Dict) -> None
        obj.pop(_generation, None)
