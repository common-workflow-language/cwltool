"""Test passing of environment variables to tools."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Union

import pytest

from cwltool.singularity import get_version

from .util import env_accepts_null, get_tool_env, needs_docker, needs_singularity

# None => accept anything, just require the key is present
# str => string equality
# Callable => call the function with the value - True => OK, False => fail
# TODO: maybe add regex?
Env = Mapping[str, str]
CheckerTypes = Union[None, str, Callable[[str, Env], bool]]
EnvChecks = Dict[str, CheckerTypes]


def assert_envvar_matches(check: CheckerTypes, k: str, env: Mapping[str, str]) -> None:
    """Assert that the check is satisfied by the key in the env."""
    if check is None:
        pass
    else:
        v = env[k]
        if isinstance(check, str):
            assert v == check, f"Environment variable {k} == {v!r} != {check!r}"
        else:
            assert check(v, env), f"Environment variable {k}={v!r} fails check."


def assert_env_matches(
    checks: EnvChecks, env: Mapping[str, str], allow_unexpected: bool = False
) -> None:
    """Assert that all checks are satisfied by the Mapping.

    Optional flag `allow_unexpected` (default = False) will allow the
    Mapping to contain extra keys which are not checked.
    """
    e = dict(env)
    for k, check in checks.items():
        assert k in e
        e.pop(k)
        assert_envvar_matches(check, k, env)

    if not allow_unexpected:
        # If we have to use env4.cwl, there may be unwanted variables
        # (see cwltool.env_to_stdout docstrings).
        # LC_CTYPE if platform has glibc
        # __CF_USER_TEXT_ENCODING on macOS
        if not env_accepts_null():
            e.pop("LC_CTYPE", None)
            e.pop("__CF_USER_TEXT_ENCODING", None)
        assert len(e) == 0, f"Unexpected environment variable(s): {', '.join(e.keys())}"


class CheckHolder(ABC):
    """Base class for check factory functions and other data required to parametrize the tests below."""

    @staticmethod
    @abstractmethod
    def checks(tmp_prefix: str) -> EnvChecks:
        """Return a mapping from environment variable names to how to check for correctness."""

    # Any flags to pass to cwltool to force use of the correct container
    flags: List[str]

    # Does the env tool (maybe in our container) accept a `-0` flag?
    env_accepts_null: bool


class NoContainer(CheckHolder):
    """No containers at all, just run in the host."""

    @staticmethod
    def checks(tmp_prefix: str) -> EnvChecks:
        """Create checks."""
        return {
            "TMPDIR": lambda v, _: v.startswith(tmp_prefix),
            "HOME": lambda v, _: v.startswith(tmp_prefix),
            "PATH": os.environ["PATH"],
        }

    flags = ["--no-container"]
    env_accepts_null = env_accepts_null()


class Docker(CheckHolder):
    """Run in a Docker container."""

    @staticmethod
    def checks(tmp_prefix: str) -> EnvChecks:
        """Create checks."""

        def HOME(v: str, env: Env) -> bool:
            # Want /whatever
            parts = os.path.split(v)
            return len(parts) == 2 and parts[0] == "/"

        return {
            "HOME": HOME,
            "TMPDIR": "/tmp",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOSTNAME": None,
        }

    flags = ["--default-container=docker.io/debian:stable-slim"]
    env_accepts_null = True


class Singularity(CheckHolder):
    """Run in a Singularity container."""

    @staticmethod
    def checks(tmp_prefix: str) -> EnvChecks:
        """Create checks."""

        def PWD(v: str, env: Env) -> bool:
            return v == env["HOME"]

        result: EnvChecks = {
            "HOME": None,
            "LANG": "C",
            "LD_LIBRARY_PATH": None,
            "PATH": None,
            "PS1": None,
            "PWD": PWD,
            "TMPDIR": "/tmp",
        }

        # Singularity variables appear to be in flux somewhat.
        version = get_version()[0]
        vmajor = version[0]
        assert vmajor == 3, "Tests only work for Singularity 3"
        vminor = version[1]
        sing_vars: EnvChecks = {
            "SINGULARITY_CONTAINER": None,
            "SINGULARITY_NAME": None,
        }
        if vminor < 5:
            sing_vars["SINGULARITY_APPNAME"] = None
        if vminor >= 5:
            sing_vars["PROMPT_COMMAND"] = None
            sing_vars["SINGULARITY_ENVIRONMENT"] = None
        if vminor == 5:
            sing_vars["SINGULARITY_INIT"] = "1"
        elif vminor > 5:
            sing_vars["SINGULARITY_COMMAND"] = "exec"
            if vminor >= 7:
                if vminor > 9:
                    sing_vars["SINGULARITY_BIND"] = ""
                else:

                    def BIND(v: str, env: Env) -> bool:
                        return v.startswith(tmp_prefix) and v.endswith(":/tmp")

                    sing_vars["SINGULARITY_BIND"] = BIND

        result.update(sing_vars)

        # Singularity automatically passes some variables through, if
        # they exist. This seems to be constant from 3.1 but isn't
        # documented (see source /internal/pkg/util/env/clean.go).
        autopass = (
            "ALL_PROXY",
            "FTP_PROXY",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "TERM",
        )
        for vname in autopass:
            if vname in os.environ:
                result[vname] = os.environ[vname]

        return result

    flags = ["--default-container=docker.io/debian:stable-slim", "--singularity"]
    env_accepts_null = True


# CRT = container runtime
CRT_PARAMS = pytest.mark.parametrize(
    "crt_params",
    [
        NoContainer(),
        pytest.param(Docker(), marks=needs_docker),
        pytest.param(Singularity(), marks=needs_singularity),
    ],
)


@CRT_PARAMS
def test_basic(crt_params: CheckHolder, tmp_path: Path, monkeypatch: Any) -> None:
    """Test that basic env vars (only) show up."""
    tmp_prefix = str(tmp_path / "canary")
    extra_env = {
        "USEDVAR": "VARVAL",
        "UNUSEDVAR": "VARVAL",
    }
    args = crt_params.flags + [f"--tmpdir-prefix={tmp_prefix}"]
    env = get_tool_env(
        tmp_path,
        args,
        extra_env=extra_env,
        monkeypatch=monkeypatch,
        runtime_env_accepts_null=crt_params.env_accepts_null,
    )
    checks = crt_params.checks(tmp_prefix)
    assert_env_matches(checks, env)


@CRT_PARAMS
def test_preserve_single(crt_params: CheckHolder, tmp_path: Path, monkeypatch: Any) -> None:
    """Test that preserving a single env var works."""
    tmp_prefix = str(tmp_path / "canary")
    extra_env = {
        "USEDVAR": "VARVAL",
        "UNUSEDVAR": "VARVAL",
    }
    args = crt_params.flags + [
        f"--tmpdir-prefix={tmp_prefix}",
        "--preserve-environment=USEDVAR",
    ]
    env = get_tool_env(
        tmp_path,
        args,
        extra_env=extra_env,
        monkeypatch=monkeypatch,
        runtime_env_accepts_null=crt_params.env_accepts_null,
    )
    checks = crt_params.checks(tmp_prefix)
    checks["USEDVAR"] = extra_env["USEDVAR"]
    assert_env_matches(checks, env)


@CRT_PARAMS
def test_preserve_all(crt_params: CheckHolder, tmp_path: Path, monkeypatch: Any) -> None:
    """Test that preserving all works."""
    tmp_prefix = str(tmp_path / "canary")
    extra_env = {
        "USEDVAR": "VARVAL",
        "UNUSEDVAR": "VARVAL",
    }
    args = crt_params.flags + [
        f"--tmpdir-prefix={tmp_prefix}",
        "--preserve-entire-environment",
    ]
    env = get_tool_env(
        tmp_path,
        args,
        extra_env=extra_env,
        monkeypatch=monkeypatch,
        runtime_env_accepts_null=crt_params.env_accepts_null,
    )
    checks = crt_params.checks(tmp_prefix)
    checks.update(extra_env)

    for vname, val in env.items():
        try:
            assert_envvar_matches(checks[vname], vname, env)
        except KeyError:
            assert val == os.environ[vname]
        except AssertionError:
            if vname == "HOME" or vname == "TMPDIR":
                # These MUST be OK
                raise
            # Other variables can be overridden
            assert val == os.environ[vname]
