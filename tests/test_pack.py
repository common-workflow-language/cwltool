import unittest
import json
from cwltool.load_tool import fetch_document, validate_document
import cwltool.pack
import cwltool.workflow

class TestPack(unittest.TestCase):
    def test_pack(self):
        self.maxDiff = None

        document_loader, workflowobj, uri = fetch_document("tests/wf/revsort.cwl")
        document_loader, avsc_names, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)
        packed = cwltool.pack.pack(document_loader, processobj, uri, metadata)
        with open("tests/wf/expect_packed.cwl") as f:
            expect_packed = json.load(f)
        self.assertEqual(expect_packed, packed)
