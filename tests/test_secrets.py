from __future__ import absolute_import

import unittest

from cwltool.secrets import SecretStore
from .util import get_data

class TestSecrets(unittest.TestCase):
    def test_secrets(self):
        secrets = SecretStore()
        job = {"foo": "bar",
               "baz": "quux"}
        secrets.store(["foo"], job)
        self.assertNotEquals(job["foo"], "bar")
        self.assertEquals(job["baz"], "quux")
        self.assertEquals(secrets.retrieve(job)["foo"], "bar")

        hello = "hello %s" % job["foo"]
        self.assertTrue(secrets.has_secret(hello))
        self.assertNotEquals(hello, "hello bar")
        self.assertEquals(secrets.retrieve(hello), "hello bar")

        hello2 = ["echo", "hello %s" % job["foo"]]
        self.assertTrue(secrets.has_secret(hello2))
        self.assertNotEquals(hello2, ["echo", "hello bar"])
        self.assertEquals(secrets.retrieve(hello2), ["echo", "hello bar"])

        hello3 = {"foo": job["foo"]}
        print(hello3)
        self.assertTrue(secrets.has_secret(hello3))
        self.assertNotEquals(hello3, {"foo": "bar"})
        self.assertEquals(secrets.retrieve(hello3), {"foo": "bar"})

        self.assertNotEquals(job["foo"], "bar")
        self.assertEquals(job["baz"], "quux")
