"""Experimental support for MPI."""
import inspect
import os
import re
from typing import List, Mapping, MutableMapping, Optional, Type, TypeVar, Union

from schema_salad.utils import yaml_no_ts

MpiConfigT = TypeVar("MpiConfigT", bound="MpiConfig")

MPIRequirementName = "http://commonwl.org/cwltool#MPIRequirement"


class MpiConfig:
    def __init__(
        self,
        runner: str = "mpirun",
        nproc_flag: str = "-n",
        default_nproc: Union[int, str] = 1,
        extra_flags: Optional[List[str]] = None,
        env_pass: Optional[List[str]] = None,
        env_pass_regex: Optional[List[str]] = None,
        env_set: Optional[Mapping[str, str]] = None,
    ) -> None:
        """
        Initialize from the argument mapping.

        Defaults are:
        runner: "mpirun"
        nproc_flag: "-n"
        default_nproc: 1
        extra_flags: []
        env_pass: []
        env_pass_regex: []
        env_set: {}

        Any unknown keys will result in an exception.
        """
        self.runner = runner
        self.nproc_flag = nproc_flag
        self.default_nproc = int(default_nproc)
        self.extra_flags = extra_flags or []
        self.env_pass = env_pass or []
        self.env_pass_regex = env_pass_regex or []
        self.env_set = env_set or {}

    @classmethod
    def load(cls: Type[MpiConfigT], config_file_name: str) -> MpiConfigT:
        """Create the MpiConfig object from the contents of a YAML file.

        The file must contain exactly one object, whose attributes must
        be in the list allowed in the class initialiser (all are
        optional).
        """
        with open(config_file_name) as cf:
            yaml = yaml_no_ts()
            data = yaml.load(cf)
        try:
            return cls(**data)
        except TypeError as e:
            unknown = set(data.keys()) - set(inspect.signature(cls).parameters)
            raise ValueError(f"Unknown key(s) in MPI configuration: {unknown}")

    def pass_through_env_vars(self, env: MutableMapping[str, str]) -> None:
        """Take the configured list of environment variables and pass them to the executed process."""
        for var in self.env_pass:
            if var in os.environ:
                env[var] = os.environ[var]

        for var_re in self.env_pass_regex:
            r = re.compile(var_re)
            for k in os.environ:
                if r.match(k):
                    env[k] = os.environ[k]

    def set_env_vars(self, env: MutableMapping[str, str]) -> None:
        """Set some variables to the value configured."""
        env.update(self.env_set)
