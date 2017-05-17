import time
import threading
import logging
from pprint import pformat

log = logging.getLogger('tes-backend')


class PollThread(threading.Thread):

    def __init__(self, operation, poll_interval=1):
        super(PollThread, self).__init__()
        self.operation = operation
        self.poll_interval = poll_interval

    def poll(self):
        raise Exception('PollThread.poll() not implemented')

    def is_done(self, operation):
        raise Exception('PollThread.is_done(operation) not implemented')

    def complete(self, operation):
        raise Exception('PollThread.complete(operation) not implemented')

    def run(self):
        while not self.is_done(self.operation):
            time.sleep(self.poll_interval)
            # slow down polling over time till it hits a max
            # if self.poll_interval < 30:
            #     self.poll_interval += 1
            log.debug(
                'POLLING ' + pformat(self.operation.get('id', "NA"))
            )

            self.operation = self.poll()

        self.complete(self.operation)
