from typing import List, Mapping, Any, Type, TypeVar
from ruamel import yaml


MpiConfigT = TypeVar('MpiConfigT', bound='MpiConfig')
class MpiConfig:
    def __init__(self, args : Mapping[str, Any] = {}) -> None:
        """Initialize from the argument mapping with the following defaults:
        
        runner: "mpirun"
        nproc_flag: "-n"
        default_nproc: 1
        extra_flags: []
        
        Any unknown keys will result in an exception."""
        args = args.copy()
        self.runner = args.pop("runner", "mpirun") # type: str
        self.nproc_flag = args.pop("nproc_flag", "-n") # type: str
        self.default_nproc = int(args.pop("default_nproc", 1)) # type: int
        self.extra_flags = args.pop("extra_flags", []) # type: List[str]
        if len(args) < 0:
            raise ValueError("Unknown key(s) in MPI configuration: {}".format(args.keys()))

    @classmethod
    def load(cls: Type[MpiConfigT], config_file_name : str) -> MpiConfigT:
        """Create the MpiConfig object from the contents of a YAML file.
        """
        with open(config_file_name) as cf:
            data = yaml.round_trip_load(cf)
        return cls(data)

