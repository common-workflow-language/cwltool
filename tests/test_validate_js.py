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

class ToolArgparse(unittest.TestCase):
    def test_get_expressions(self):
        test_cwl_yaml = yaml.round_trip_load(TEST_CWL)
        schema = process.get_schema("v1.0")[1].names["CommandLineTool"]

        exprs = get_expressions(test_cwl_yaml, schema)

        self.assertEqual(len(exprs), 1)

    @mock.patch("cwltool.validate_js.print_js_hint_messages")
    def test_validate_js_expressions(self, print_js_hint_messages):
        test_cwl_yaml = yaml.round_trip_load(TEST_CWL)
        schema = process.get_schema("v1.0")[1].names["CommandLineTool"]

        validate_js_expressions(test_cwl_yaml, schema)

        assert print_js_hint_messages.call_args is not None
        assert len(print_js_hint_messages.call_args[0]) > 0

    def test_jshint_js(self):
        result1 = jshint_js("""
        function funcName(){
        }
        """, [])

        self.assertEquals(result1[0], [])
        self.assertEquals(result1[1], ["funcName"])

        assert len(jshint_js("<INVALID JS>")[0]) > 1

        # test es6 syntax
        self.assertEquals(len(jshint_js(code_fragment_to_js("((() => 4)())"), [])[0]), 1)

        self.assertEquals(len(jshint_js(code_fragment_to_js("undefined_name()"))[0]), 1)

        self.assertEquals(len(jshint_js(code_fragment_to_js("defined_name()"), ["defined_name"])[0]), 0)
