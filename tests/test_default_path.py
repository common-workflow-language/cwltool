import unittest

from schema_salad.ref_resolver import Loader

from cwltool.load_tool import fetch_document, validate_document

from .util import get_data


class TestDefaultPath(unittest.TestCase):
    def test_default_path(self):
        """Testing that error is not raised when default path is not present"""
        document_loader, workflowobj, uri = fetch_document(
            get_data("tests/wf/default_path.cwl"))
        document_loader, avsc_names, processobj, metadata, uri = validate_document(
            document_loader, workflowobj, uri)

        self.assertIsInstance(document_loader,Loader)
        self.assertIn("cwlVersion",processobj)
