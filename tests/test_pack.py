from __future__ import absolute_import

import json
import unittest

import os
from functools import partial
import tempfile

import pytest
from six import StringIO

import cwltool.pack
import cwltool.workflow
from cwltool.resolver import tool_resolver
from cwltool import load_tool
from cwltool.load_tool import fetch_document, validate_document
from cwltool.main import makeRelative, main, print_pack
from cwltool.pathmapper import adjustDirObjs, adjustFileObjs
from cwltool.utils import onWindows
from .util import get_data


class TestPack(unittest.TestCase):
    maxDiff = None

    def test_pack(self):
        load_tool.loaders = {}

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

        # Testing single tool workflow
        document_loader, workflowobj, uri = fetch_document(
            get_data("tests/wf/hello_single_tool.cwl"))
        document_loader, _, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)
        # generate pack output dict
        packed = json.loads(print_pack(document_loader, processobj, uri, metadata))

        self.assertEqual('v1.0', packed["cwlVersion"])

        # Testing single step workflow
        document_loader, workflowobj, uri = fetch_document(
            get_data("tests/wf/hello-workflow.cwl"))
        document_loader, _, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)
        # generate pack output dict
        packed = json.loads(print_pack(document_loader, processobj, uri, metadata))

        self.assertEqual('v1.0', packed["cwlVersion"])

    def test_pack_idempotence_tool(self):
        """Test to ensure that pack produces exactly the same document for
           an already packed document"""

        # Testing single tool
        self._pack_idempotently("tests/wf/hello_single_tool.cwl")

    def test_pack_idempotence_workflow(self):
        """Test to ensure that pack produces exactly the same document for
           an already packed document"""

        # Testing workflow
        self._pack_idempotently("tests/wf/count-lines1-wf.cwl")

    def _pack_idempotently(self, document):
        document_loader, workflowobj, uri = fetch_document(
            get_data(document))
        document_loader, avsc_names, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)
        # generate pack output dict
        packed = json.loads(print_pack(document_loader, processobj, uri, metadata))

        document_loader, workflowobj, uri2 = fetch_document(packed)
        document_loader, avsc_names, processobj, metadata, uri2 = validate_document(
            document_loader, workflowobj, uri)
        double_packed = json.loads(print_pack(document_loader, processobj, uri2, metadata))
        self.assertEqual(packed, double_packed)

    @pytest.mark.skipif(onWindows(),
                        reason="Instance of cwltool is used, on Windows it invokes a default docker container"
                               "which is not supported on AppVeyor")
    def test_packed_workflow_execution(self):
        load_tool.loaders = {}
        test_wf = "tests/wf/count-lines1-wf.cwl"
        test_wf_job = "tests/wf/wc-job.json"
        document_loader, workflowobj, uri = fetch_document(
            get_data(test_wf), resolver=tool_resolver)
        document_loader, avsc_names, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)
        packed = json.loads(print_pack(document_loader, processobj, uri, metadata))
        temp_packed_path = tempfile.mkstemp()[1]
        with open(temp_packed_path, 'w') as f:
            json.dump(packed, f)
        normal_output = StringIO()
        packed_output = StringIO()
        self.assertEquals(main(['--debug', get_data(temp_packed_path),
                                get_data(test_wf_job)],
                               stdout=packed_output), 0)
        self.assertEquals(main([get_data(test_wf),
                                get_data(test_wf_job)],
                               stdout=normal_output), 0)
        self.assertEquals(json.loads(packed_output.getvalue()), json.loads(normal_output.getvalue()))
        os.remove(temp_packed_path)

    @pytest.mark.skipif(onWindows(),
                        reason="Instance of cwltool is used, on Windows it invokes a default docker container"
                               "which is not supported on AppVeyor")
    def test_preserving_namespaces(self):
        test_wf = "tests/wf/formattest.cwl"
        test_wf_job = "tests/wf/formattest-job.json"
        document_loader, workflowobj, uri = fetch_document(
            get_data(test_wf))
        document_loader, avsc_names, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)
        packed = json.loads(print_pack(document_loader, processobj, uri, metadata))
        assert "$namespaces" in packed
        temp_packed_path = tempfile.mkstemp()[1]
        with open(temp_packed_path, 'w') as f:
            json.dump(packed, f)
        normal_output = StringIO()
        packed_output = StringIO()
        self.assertEquals(main(['--debug', get_data(temp_packed_path),
                                get_data(test_wf_job)],
                               stdout=packed_output), 0)
        self.assertEquals(main([get_data(test_wf),
                                get_data(test_wf_job)],
                               stdout=normal_output), 0)
        self.assertEquals(json.loads(packed_output.getvalue()), json.loads(normal_output.getvalue()))
        os.remove(temp_packed_path)
