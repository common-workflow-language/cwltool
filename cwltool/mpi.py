import os
import re
from typing import List, Dict, Any, Type, TypeVar, MutableMapping
from ruamel import yaml


MpiConfigT = TypeVar("MpiConfigT", bound="MpiConfig")


class MpiConfig:
    def __init__(self, args: Dict[str, Any] = {}) -> None:
        """Initialize from the argument mapping with the following defaults:
        
        runner: "mpirun"
        nproc_flag: "-n"
        default_nproc: 1
        extra_flags: []
        env_pass: []
        env_pass_regex: []
        env_set: {}

        Any unknown keys will result in an exception."""
        args = args.copy()
        self.runner = args.pop("runner", "mpirun")  # type: str
        self.nproc_flag = args.pop("nproc_flag", "-n")  # type: str
        self.default_nproc = int(args.pop("default_nproc", 1))  # type: int
        self.extra_flags = args.pop("extra_flags", [])  # type: List[str]
        self.env_pass = args.pop("env_pass", [])  # type: List[str]
        self.env_pass_regex = args.pop("env_pass_regex", [])  # type: List[str]
        self.env_set = args.pop("env_set", {})  # type: Dict[str, str]

        if len(args) > 0:
            raise ValueError(
                "Unknown key(s) in MPI configuration: {}".format(args.keys())
            )

    @classmethod
    def load(cls: Type[MpiConfigT], config_file_name: str) -> MpiConfigT:
        """Create the MpiConfig object from the contents of a YAML file.
        """
        with open(config_file_name) as cf:
            data = yaml.round_trip_load(cf)
        return cls(data)

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
