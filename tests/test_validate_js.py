from ruamel import yaml

from cwltool import process
from cwltool.sandboxjs import code_fragment_to_js
from cwltool import validate_js

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

def test_get_expressions():
    test_cwl_yaml = yaml.round_trip_load(TEST_CWL)
    schema = process.get_schema("v1.0")[1].names["CommandLineTool"]

    exprs = validate_js.get_expressions(test_cwl_yaml, schema)

    assert len(exprs) == 1


def test_validate_js_expressions(mocker):
    test_cwl_yaml = yaml.round_trip_load(TEST_CWL)
    schema = process.get_schema("v1.0")[1].names["CommandLineTool"]

    mocker.patch("cwltool.validate_js.print_js_hint_messages")
    validate_js.validate_js_expressions(test_cwl_yaml, schema)

    assert validate_js.print_js_hint_messages.call_args is not None
    assert len(validate_js.print_js_hint_messages.call_args[0]) > 0

def test_js_hint_basic():
    result = validate_js.jshint_js("""
    function funcName(){
    }
    """, [])

    assert result.errors == []
    assert result.globals == ["funcName"]

def test_js_hint_reports_invalid_js():
    assert len(validate_js.jshint_js("<INVALID JS>").errors) > 1

def test_js_hint_warn_on_es6():
    assert len(validate_js.jshint_js(code_fragment_to_js("((() => 4)())"), []).errors) == 1

def test_js_hint_error_on_undefined_name():
    assert len(validate_js.jshint_js(code_fragment_to_js("undefined_name()")).errors) == 1

def test_js_hint_set_defined_name():
    assert len(validate_js.jshint_js(code_fragment_to_js("defined_name()"), ["defined_name"]).errors) == 0
