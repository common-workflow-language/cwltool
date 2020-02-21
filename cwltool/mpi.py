from typing import List, MutableMapping
from .context import RuntimeContext
from .job import CommandLineJob

class MpiEnv:
    def __init__(self, runtimeContext : RuntimeContext) -> None:
        """Initialize."""
        self.run = "mpirun" if runtimeContext.mpi_run is None else runtimeContext.mpi_run
        self.tasks_flag = "-n" if runtimeContext.mpi_tasks_flag is None else runtimeContext.mpi_tasks_flag
        self.tasks = 1 if runtimeContext.mpi_tasks is None else runtimeContext.mpi_tasks
        self.extra = runtimeContext.mpi_extra

class MpiCommandLineJob(CommandLineJob):
    """Runs a CommandLineJob in parallel using mpirun or similar."""

    # Really we should override run(), but all we need is to intercept
    # the call to _execute, insert our mpirun -np n as the first (non
    # self) argument and then call the base class _execute.
    def _execute(
        self,
        runtime: List[str],
        env: MutableMapping[str, str],
        runtimeContext: RuntimeContext,
        monitor_function=None,  # type: Optional[Callable[[subprocess.Popen[str]], None]]
    ) -> None:
        if runtimeContext.mpi_on:
            assert runtime == [], "MPI command line job requires an empty runtime list"
            menv = MpiEnv(runtimeContext)
            mpiflags = [menv.run, menv.tasks_flag, menv.tasks] + menv.extra
            runtime = mpiflags + runtime

        super(MpiCommandLineJob, self)._execute(runtime, env, runtimeContext, monitor_function)
