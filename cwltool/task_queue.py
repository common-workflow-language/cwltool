# Copyright (C) The Arvados Authors. All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0
"""TaskQueue."""

import queue
import threading
from typing import Callable, Optional

from .loghandler import _logger


class TaskQueue:
    """A TaskQueue class.

    Uses a first-in, first-out queue of tasks executed on a fixed number of
    threads.

    New tasks enter the queue and are started in the order received,
    as worker threads become available.

    If thread_count == 0 then tasks will be synchronously executed
    when add() is called (this makes the actual task queue behavior a
    no-op, but may be a useful configuration knob).

    The thread_count is also used as the maximum size of the queue.

    The threads are created during TaskQueue initialization.  Call
    join() when you're done with the TaskQueue and want the threads to
    stop.
    """

    in_flight: int = 0
    """The number of tasks in the queue."""

    def __init__(self, lock: threading.Lock, thread_count: int):
        """Create a new task queue using the specified lock and number of threads."""
        self.thread_count = thread_count
        self.task_queue: queue.Queue[Optional[Callable[[], None]]] = queue.Queue(
            maxsize=self.thread_count
        )
        self.task_queue_threads = []
        self.lock = lock
        self.error: Optional[BaseException] = None

        for _r in range(0, self.thread_count):
            t = threading.Thread(target=self._task_queue_func)
            self.task_queue_threads.append(t)
            t.start()

    def _task_queue_func(self) -> None:
        while True:
            task = self.task_queue.get()
            if task is None:
                return
            try:
                task()
            except BaseException as e:  # noqa: B036
                _logger.exception("Unhandled exception running task", exc_info=e)
                self.error = e
            finally:
                with self.lock:
                    self.in_flight -= 1

    def add(
        self,
        task: Callable[[], None],
        unlock: Optional[threading.Condition] = None,
        check_done: Optional[threading.Event] = None,
    ) -> None:
        """
        Add your task to the queue.

        The optional unlock will be released prior to attempting to add the
        task to the queue.

        If the optional "check_done" threading.Event's flag is set, then we
        will skip adding this task to the queue.

        If the TaskQueue was created with thread_count == 0 then your task will
        be synchronously executed.

        """
        if self.thread_count == 0:
            task()
            return

        with self.lock:
            self.in_flight += 1

        while True:
            try:
                if unlock is not None:
                    unlock.release()
                if check_done is not None and check_done.is_set():
                    with self.lock:
                        self.in_flight -= 1
                    return
                self.task_queue.put(task, block=True, timeout=3)
                return
            except queue.Full:
                pass
            finally:
                if unlock is not None:
                    unlock.acquire()

    def drain(self) -> None:
        """Drain the queue."""
        try:
            while not self.task_queue.empty():
                self.task_queue.get(True, 0.1)
        except queue.Empty:
            pass

    def join(self) -> None:
        """Wait for all threads to complete."""
        for _t in self.task_queue_threads:
            self.task_queue.put(None)
        for t in self.task_queue_threads:
            t.join()
