from __future__ import absolute_import
import json
import os
import unittest
from functools import partial

import cwltool.pack
from cwltool.main import print_pack as print_pack
import cwltool.workflow
from cwltool.load_tool import fetch_document, validate_document
from cwltool.main import makeRelative
from cwltool.pathmapper import adjustDirObjs, adjustFileObjs

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

    def test_pack_missing_cwlVersion(self):
        """Test to ensure the generated pack output is not missing
        the `cwlVersion` in case of single tool workflow and single step workflow"""
        # Since diff is longer than 3174 characters
        self.maxDiff = None

        # Testing single tool workflow
        document_loader, workflowobj, uri = fetch_document(
            get_data("tests/wf/hello_single_tool.cwl"))
        document_loader, avsc_names, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)
        # generate pack output dict
        packed = json.loads(print_pack(document_loader, processobj, uri, metadata))

        self.assertEqual('v1.0', packed["cwlVersion"])

        # Testing single step workflow
        document_loader, workflowobj, uri = fetch_document(
            get_data("tests/wf/hello-workflow.cwl"))
        document_loader, avsc_names, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)
        # generate pack output dict
        packed = json.loads(print_pack(document_loader, processobj, uri, metadata))

        self.assertEqual('v1.0', packed["cwlVersion"])
