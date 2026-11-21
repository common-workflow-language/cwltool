"""Enables Docker software containers via the udocker runtime."""

from .docker import DockerCommandLineJob


class UDockerCommandLineJob(DockerCommandLineJob):
    """Runs a CommandLineJob in a software container using the udocker engine."""

    @staticmethod
    def append_volume(
        runtime: list[str],
        source: str,
        target: str,
        writable: bool = False,
        skip_mkdirs: bool = False,
    ) -> None:
        """Add binding arguments to the runtime list."""
        runtime.append("--volume={}:{}:{}".format(source, target, "rw" if writable else "ro"))
