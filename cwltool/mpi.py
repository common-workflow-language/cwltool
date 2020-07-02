import os
import re
import inspect
from typing import List, Type, TypeVar, MutableMapping, Mapping, Union
from ruamel import yaml


MpiConfigT = TypeVar("MpiConfigT", bound="MpiConfig")

MPIRequirementName = "http://commonwl.org/cwltool#MPIRequirement"

class MpiConfig:
    def __init__(
        self,
        runner: str = "mpirun",
        nproc_flag: str = "-n",
        default_nproc: Union[int, str] = 1,
        extra_flags: List[str] = [],
        env_pass: List[str] = [],
        env_pass_regex: List[str] = [],
        env_set: Mapping[str, str] = {},
    ) -> None:
        """Initialize from the argument mapping with the following defaults:

        runner: "mpirun"
        nproc_flag: "-n"
        default_nproc: 1
        extra_flags: []
        env_pass: []
        env_pass_regex: []
        env_set: {}

        Any unknown keys will result in an exception."""
        self.runner = runner
        self.nproc_flag = nproc_flag
        self.default_nproc = int(default_nproc)
        self.extra_flags = extra_flags
        self.env_pass = env_pass
        self.env_pass_regex = env_pass_regex
        self.env_set = env_set

    @classmethod
    def load(cls: Type[MpiConfigT], config_file_name: str) -> MpiConfigT:
        """Create the MpiConfig object from the contents of a YAML file.

        The file must contain exactly one object, whose attributes must
        be in the list allowed in the class initialiser (all are
        optional).
        """
        with open(config_file_name) as cf:
            data = yaml.round_trip_load(cf)
        try:
            return cls(**data)
        except TypeError as e:
            unknown = set(data.keys()) - set(inspect.signature(cls).parameters)
            raise ValueError("Unknown key(s) in MPI configuration: {}".format(unknown))

    def pass_through_env_vars(self, env: MutableMapping[str, str]) -> None:
        """Here we take the configured list of environment variables and
        simply pass them through to the executed process.
        """
        for var in self.env_pass:
            if var in os.environ:
                env[var] = os.environ[var]

        for var_re in self.env_pass_regex:
            r = re.compile(var_re)
            for k in os.environ:
                if r.match(k):
                    env[k] = os.environ[k]

    def set_env_vars(self, env: MutableMapping[str, str]) -> None:
        """Here we set some variables to the value configured.
        """
        env.update(self.env_set)
