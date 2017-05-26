from __future__ import print_function

import logging
import os
import signal
import subprocess
import tempfile
import time
import unittest
import yaml


WORK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "test_work")


def popen(*args, **kwargs):
    kwargs['preexec_fn'] = os.setsid
    return subprocess.Popen(*args, **kwargs)


def kill(p):
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        p.wait()
    except OSError:
        pass


def get_abspath(path):
    return os.path.join(os.path.dirname(__file__), path)


def which(file):
    for path in os.environ["PATH"].split(":"):
        p = os.path.join(path, file)
        if os.path.exists(p):
            return p


def temp_config(config):
    configFile = tempfile.NamedTemporaryFile(delete=False)
    yaml.dump(config, configFile)
    return configFile


def config_seconds(sec):
    # The funnel config is currently parsed as nanoseconds
    # this helper makes that manageale
    return int(sec * 1000000000)


class SimpleServerTest(unittest.TestCase):

    def setUp(self):
        self.addCleanup(self.cleanup)
        self.testdir = os.path.dirname(os.path.realpath(__file__))
        self.rootprojectdir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.realpath(__file__)
        )))
        self.tmpdir = os.path.join(self.testdir, "test_tmp")
        if not os.path.exists(self.tmpdir):
            os.mkdir(self.tmpdir)
        self.task_server = None
        f, db_path = tempfile.mkstemp(dir=self.tmpdir, prefix="tes_task_db.")
        os.close(f)
        self.storage_dir = os.path.abspath(db_path + ".storage")
        self.funnel_work_dir = os.path.abspath(db_path + ".work-dir")
        os.mkdir(self.storage_dir)
        os.mkdir(self.funnel_work_dir)

        # Build server config file (YAML)
        rate = config_seconds(0.05)
        configFile = temp_config({
            "HostName": "localhost",
            "HTTPPort": "8000",
            "RPCPort": "9090",
            "DBPath": db_path,
            "WorkDir": self.funnel_work_dir,
            "Storage": [{
                "Local": {
                    "AllowedDirs": [self.rootprojectdir]
                }
            }],
            "LogLevel": "debug",
            "Worker": {
                "Timeout": -1,
                "StatusPollRate": rate,
                "LogUpdateRate": rate,
                "NewJobPollRate": rate,
                "UpdateRate": rate,
                "TrackerRate": rate
            },
            "ScheduleRate": rate,
        })

        # Start server
        cmd = ["funnel", "server", "--config", configFile.name]
        logging.info("Running %s" % (" ".join(cmd)))
        self.task_server = popen(cmd)
        signal.signal(signal.SIGINT, self.cleanup)
        time.sleep(1)

    # We're using this instead of tearDown because python doesn't call tearDown
    # if setUp fails. Since our setUp is complex, that means things don't get
    # properly cleaned up (e.g. processes are orphaned).
    def cleanup(self, *args):
        if self.task_server is not None:
            kill(self.task_server)
