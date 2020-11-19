# Copyright (C) The Arvados Authors. All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0
"""TaskQueue."""

import queue
import threading

from typing import Callable, Optional

from .loghandler import _logger


class TaskQueue(object):
    """
    A TaskQueue class.

    Uses a first-in, first-out queue of tasks executed on a fixed number of
    threads.

    If thread_count == 1 then as you add() tasks they will be immediately
    executed. Otherwise new tasks enter the queue and will be executed in
    the order received.

    The thread_count is also used as the maximum size of the queue.

    The threads are created during TaskQueue initialization, so delay the
    creation of a TaskQueue until you really need it.


    Attributes
    ----------
    in_flight
        the number of tasks in the queue
    """

    def __init__(self, lock: threading.Lock, thread_count: int):
        self.thread_count = thread_count
        self.task_queue: queue.Queue[Optional[Callable[[], None]]] = queue.Queue(
            maxsize=self.thread_count
        )
        self.task_queue_threads = []
        self.lock = lock
        self.in_flight = 0
        self.error: Optional[Exception] = None

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
            except BaseException as e:
                _logger.exception("Unhandled exception running task")
                self.error = e

            with self.lock:
                self.in_flight -= 1

    def add(
        self,
        task: Callable[[], None],
        unlock: Optional[threading.Lock] = None,
        check_done: Optional[threading.Event] = None,
    ) -> None:
        """
        Add your task to the queue.

        If the TaskQueue was created with only one thread then your task will
        be immediately executed.

        The optional unlock will be released prior to attempting to add the
        task to the queue.

        If the optional "check_done" threading.Event's flag is set, then we
        will skip adding this task to the queue.
        """
        if self.thread_count > 1:
            with self.lock:
                self.in_flight += 1
        else:
            task()
            return

        while True:
            try:
                if unlock is not None:
                    unlock.release()
                if check_done is not None:
                    if check_done.is_set():
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
