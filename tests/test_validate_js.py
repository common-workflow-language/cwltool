import unittest
import mock

from ruamel import yaml
from schema_salad.schema import get_metaschema

from cwltool import process
from cwltool.validate_js import (get_expressions, jshint_js,
                                 validate_js_expressions)
from cwltool.sandboxjs import code_fragment_to_js


TEST_CWL = """
cwlVersion: v1.0
class: CommandLineTool
baseCommand: echo

requirements:
  - class: InlineJavascriptRequirement
inputs:
  - id: parameter
    inputBinding:
      valueFrom: string before $(kjdbfkjd) string after
    type: string?

outputs: []
"""

class TestGetExpressions(unittest.TestCase):
    def test_get_expressions(self):
        test_cwl_yaml = yaml.round_trip_load(TEST_CWL)
        schema = process.get_schema("v1.0")[1].names["CommandLineTool"]

        exprs = get_expressions(test_cwl_yaml, schema)

        self.assertEqual(len(exprs), 1)


class TestValidateJsExpressions(unittest.TestCase):
    @mock.patch("cwltool.validate_js.print_js_hint_messages")
    def test_validate_js_expressions(self, print_js_hint_messages):
        test_cwl_yaml = yaml.round_trip_load(TEST_CWL)
        schema = process.get_schema("v1.0")[1].names["CommandLineTool"]

        validate_js_expressions(test_cwl_yaml, schema)

        assert print_js_hint_messages.call_args is not None
        assert len(print_js_hint_messages.call_args[0]) > 0

class TestJSHintJS(unittest.TestCase):
    def test_basic_usage(self):
        result = jshint_js("""
        function funcName(){
        }
        """, [])

        self.assertEquals(result.errors, [])
        self.assertEquals(result.globals, ["funcName"])

    def test_reports_invalid_js(self):
        assert len(jshint_js("<INVALID JS>").errors) > 1

    def test_warn_on_es6(self):
        self.assertEquals(len(jshint_js(code_fragment_to_js("((() => 4)())"), []).errors), 1)

    def test_error_on_undefined_name(self):
        self.assertEquals(len(jshint_js(code_fragment_to_js("undefined_name()")).errors), 1)

    def test_set_defined_name(self):
        self.assertEquals(len(jshint_js(code_fragment_to_js("defined_name()"), ["defined_name"]).errors), 0)
