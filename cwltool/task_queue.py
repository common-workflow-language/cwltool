# Copyright (C) The Arvados Authors. All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0

import queue
import threading
import logging

from typing import Callable, Optional

logger = logging.getLogger("arvados.cwl-runner")


class TaskQueue(object):
    def __init__(self, lock: threading.Lock, thread_count: int):
        self.thread_count = thread_count
        self.task_queue: queue.Queue[Optional[Callable[[], None]]] = queue.Queue(
            maxsize=self.thread_count
        )
        self.task_queue_threads = []
        self.lock = lock
        self.in_flight = 0
        self.error: Optional[Exception] = None

        for r in range(0, self.thread_count):
            t = threading.Thread(target=self.task_queue_func)
            self.task_queue_threads.append(t)
            t.start()

    def task_queue_func(self) -> None:
        while True:
            task = self.task_queue.get()
            if task is None:
                return
            try:
                task()
            except Exception as e:
                logger.exception("Unhandled exception running task")
                self.error = e

            with self.lock:
                self.in_flight -= 1

    def add(
        self,
        task: Callable[[], None],
        unlock: Optional[threading.Lock] = None,
        check_done: Optional[threading.Event] = None,
    ) -> None:
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
        try:
            # Drain queue
            while not self.task_queue.empty():
                self.task_queue.get(True, 0.1)
        except queue.Empty:
            pass

    def join(self) -> None:
        for t in self.task_queue_threads:
            self.task_queue.put(None)
        for t in self.task_queue_threads:
            t.join()
