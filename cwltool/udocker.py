"""Enables Docker software containers via the udocker runtime."""

from typing import List

from .docker import DockerCommandLineJob


class UDockerCommandLineJob(DockerCommandLineJob):
    """Runs a CommandLineJob in a sofware container using the udocker engine."""

    def append_volume(
        self, runtime: List[str], source: str, target: str, writable: bool = False
    ) -> None:
        """Add binding arguments to the runtime list."""
        runtime.append(
            "--volume={}:{}:{}".format(source, target, "rw" if writable else "ro")
        )
