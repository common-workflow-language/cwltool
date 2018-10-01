import copy
import itertools
import json
import logging
from collections import namedtuple
from typing import (Any, Dict, List, MutableMapping, MutableSequence, Optional,
                    Tuple, Union)

import avro.schema  # always import after schema_salad, never before
from pkg_resources import resource_stream
from ruamel.yaml.comments import CommentedMap  # pylint: disable=unused-import
from schema_salad.sourceline import SourceLine
from schema_salad.validate import Schema  # pylint: disable=unused-import
from schema_salad.validate import ValidationException, validate_ex
from six import string_types
from typing_extensions import Text  # pylint: disable=unused-import
# move to a regular typing import when Python 3.3-3.6 is no longer supported

from .expression import scanner as scan_expression
from .loghandler import _logger
from .sandboxjs import code_fragment_to_js, exec_js_process
from .utils import json_dumps


def is_expression(tool, schema):
    # type: (Union[CommentedMap, Any], Optional[Schema]) -> bool
    return isinstance(schema, avro.schema.EnumSchema) \
        and schema.name == "Expression" and isinstance(tool, string_types)

class SuppressLog(logging.Filter):
    def __init__(self, name):  # type: (Text) -> None
        name = str(name)
        super(SuppressLog, self).__init__(name)

    def filter(self, record):
        return False


_logger_validation_warnings = logging.getLogger("cwltool.validation_warnings")
_logger_validation_warnings.addFilter(SuppressLog("cwltool.validation_warnings"))

def get_expressions(tool,             # type: Union[CommentedMap, Any]
                    schema,           # type: Optional[avro.schema.Schema]
                    source_line=None  # type: Optional[SourceLine]
                   ):  # type: (...) -> List[Tuple[Text, Optional[SourceLine]]]
    if is_expression(tool, schema):
        return [(tool, source_line)]
    elif isinstance(schema, avro.schema.UnionSchema):
        valid_schema = None

        for possible_schema in schema.schemas:
            if is_expression(tool, possible_schema):
                return [(tool, source_line)]
            elif validate_ex(possible_schema, tool, raise_ex=False,
                             logger=_logger_validation_warnings):
                valid_schema = possible_schema

        return get_expressions(tool, valid_schema, source_line)
    elif isinstance(schema, avro.schema.ArraySchema):
        if not isinstance(tool, MutableSequence):
            return []

        return list(itertools.chain(*
            map(lambda x: get_expressions(x[1], schema.items, SourceLine(tool, x[0])), enumerate(tool))  # type: ignore # https://github.com/python/mypy/issues/4679
        ))

    elif isinstance(schema, avro.schema.RecordSchema):
        if not isinstance(tool, MutableMapping):
            return []

        expression_nodes = []

        for schema_field in schema.fields:
            if schema_field.name in tool:
                expression_nodes.extend(get_expressions(
                    tool[schema_field.name],
                    schema_field.type,
                    SourceLine(tool, schema_field.name)
                ))

        return expression_nodes
    else:
        return []


JSHintJSReturn = namedtuple("jshint_return", ["errors", "globals"])

def jshint_js(js_text, globals=None, options=None):
    # type: (Text, List[Text], Dict) -> Tuple[List[Text], List[Text]]
    if globals is None:
        globals = []
    if options is None:
        options = {
            "includewarnings": [
                "W117",  # <VARIABLE> not defined
                "W104", "W119"  # using ES6 features
            ],
            "strict": "implied",
            "esversion": 5
        }

    with resource_stream(__name__, "jshint/jshint.js") as file:
        # NOTE: we need a global variable for lodash (which jshint depends on)
        jshint_functions_text = "var global = this;" + file.read().decode('utf-8')

    with resource_stream(__name__, "jshint/jshint_wrapper.js") as file:
        # NOTE: we need to assign to ob, as the expression {validateJS: validateJS} as an expression
        # is interpreted as a block with a label `validateJS`
        jshint_functions_text += "\n" + file.read().decode('utf-8') + "\nvar ob = {validateJS: validateJS}; ob"

    returncode, stdout, stderr = exec_js_process(
        "validateJS(%s)" % json_dumps({
            "code": js_text,
            "options": options,
            "globals": globals
        }),
        timeout=30,
        context=jshint_functions_text
    )

    def dump_jshint_error():
        # type: () -> None
        raise RuntimeError("jshint failed to run succesfully\nreturncode: %d\nstdout: \"%s\"\nstderr: \"%s\"" % (
            returncode,
            stdout,
            stderr
        ))

    if returncode == -1:
        _logger.warn("jshint process timed out")

    if returncode != 0:
        dump_jshint_error()

    try:
        jshint_json = json.loads(stdout)
    except ValueError:
        dump_jshint_error()

    jshint_errors = []  # type: List[Text]

    js_text_lines = js_text.split("\n")

    for jshint_error_obj in jshint_json.get("errors", []):
        text = u"JSHINT: " + js_text_lines[jshint_error_obj["line"] - 1] + "\n"
        text += u"JSHINT: " + " " * (jshint_error_obj["character"] - 1) + "^\n"
        text += u"JSHINT: %s: %s" % (jshint_error_obj["code"], jshint_error_obj["reason"])
        jshint_errors.append(text)

    return JSHintJSReturn(jshint_errors, jshint_json.get("globals", []))


def print_js_hint_messages(js_hint_messages, source_line):
    # type: (List[Text], Optional[SourceLine]) -> None
    if source_line:
        for js_hint_message in js_hint_messages:
            _logger.warn(source_line.makeError(js_hint_message))

def validate_js_expressions(tool, schema, jshint_options=None):
    # type: (CommentedMap, Schema, Dict) -> None

    if tool.get("requirements") is None:
        return

    requirements = tool["requirements"]

    default_globals = [u"self", u"inputs", u"runtime", u"console"]

    for i, prop in enumerate(reversed(requirements)):
        if prop["class"] == "InlineJavascriptRequirement":
            expression_lib = prop.get("expressionLib", [])
            break
    else:
        return

    js_globals = copy.deepcopy(default_globals)

    for i, expression_lib_line in enumerate(expression_lib):
        expression_lib_line_errors, expression_lib_line_globals = jshint_js(expression_lib_line, js_globals, jshint_options)
        js_globals.extend(expression_lib_line_globals)
        print_js_hint_messages(expression_lib_line_errors, SourceLine(expression_lib, i))

    expressions = get_expressions(tool, schema)

    for expression, source_line in expressions:
        unscanned_str = expression.strip()
        scan_slice = scan_expression(unscanned_str)

        while scan_slice:
            if unscanned_str[scan_slice[0]] == '$':
                code_fragment = unscanned_str[scan_slice[0] + 1:scan_slice[1]]
                code_fragment_js = code_fragment_to_js(code_fragment, "")
                expression_errors, _ = jshint_js(code_fragment_js, js_globals, jshint_options)
                print_js_hint_messages(expression_errors, source_line)

            unscanned_str = unscanned_str[scan_slice[1]:]
            scan_slice = scan_expression(unscanned_str)
