import json
import os
import unittest
from functools import partial

import cwltool.pack
import cwltool.workflow
from cwltool.load_tool import fetch_document, validate_document
from cwltool.main import makeRelative
from cwltool.process import adjustFileObjs, adjustDirObjs
from .util import get_data

class TestPack(unittest.TestCase):
    def test_pack(self):
        self.maxDiff = None

        document_loader, workflowobj, uri = fetch_document(
            get_data("tests/wf/revsort.cwl"))
        document_loader, avsc_names, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)
        packed = cwltool.pack.pack(document_loader, processobj, uri, metadata)
        with open(get_data("tests/wf/expect_packed.cwl")) as f:
            expect_packed = json.load(f)
        adjustFileObjs(packed, partial(makeRelative,
            os.path.abspath(get_data("tests/wf"))))
        adjustDirObjs(packed, partial(makeRelative,
            os.path.abspath(get_data("tests/wf"))))
        self.assertIn("$schemas", packed)
        del packed["$schemas"]
        del expect_packed["$schemas"]

        self.assertEqual(expect_packed, packed)
