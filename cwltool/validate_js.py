import functools
import itertools
import json
import logging
from os import path
from typing import Any, Dict, List, Tuple, Union

import avro.schema
from pkg_resources import resource_filename
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from schema_salad.sourceline import SourceLine
from schema_salad.validate import ValidationException, validate_ex

from . import process
from .draft2tool import CommandLineTool
from .expression import scanner as scan_expression
from .process import Process
from .sandboxjs import code_fragment_to_js, exec_js_process, execjs

_logger = logging.getLogger("cwltool")

def is_expression(tool, schema):
    # type: (Union[CommentedMap, Any], avro.schema.Schema) -> bool
    return isinstance(schema, avro.schema.EnumSchema) and schema.name == "Expression" and isinstance(tool, str)

def get_expressions(tool, schema, source_line=None):
    # type: (Union[CommentedMap, Any], avro.schema.Schema, SourceLine) -> List[Tuple[str, SourceLine]]
    if is_expression(tool, schema):
        return [(tool, source_line)]
    elif isinstance(schema, avro.schema.UnionSchema):
        valid_schema = None

        for possible_schema in schema.schemas:
            if is_expression(tool, possible_schema):
                return [(tool, source_line)]
            elif validate_ex(possible_schema, tool, raise_ex=False):
                valid_schema = possible_schema

        return get_expressions(tool, valid_schema, source_line)
    elif isinstance(schema, avro.schema.ArraySchema):
        if not isinstance(tool, list):
            return []

        return list(itertools.chain(*
            map(lambda x: get_expressions(x[1], schema.items, SourceLine(tool, x[0])), enumerate(tool))
        ))
    elif isinstance(schema, avro.schema.RecordSchema):
        if not isinstance(tool, Dict):
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

def should_include_jshint_message(error_code):
    # type: (str) -> bool
    include_warnings = [
        "W117", # <VARIABLE> not defined
        "W104", "W119"  # using ES6 features
    ]

    return error_code[0] == "E" or error_code in include_warnings


def jshint_js(js_text, globals = None):
    # type: (str, List[str]) -> Tuple[List[str], List[str]]
    if globals is None:
        globals = []
    linter_folder = resource_filename(__name__, "jshint")

    returncode, stdout, stderr = exec_js_process(
        path.join(linter_folder, "jshint_wrapper.js"),
        json.dumps({
            "code": js_text,
            "globals": globals
        })
    )

    def dump_jshint_error():
        raise RuntimeError("jshint failed to run succesfully\nreturncode %s\nstdout: %s\nstderr: %s" % (
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

    jshint_errors = [] # type: List[str]

    for jshint_error_obj in jshint_json.get("errors", []) :
        if should_include_jshint_message(jshint_error_obj["code"]):
            if jshint_error_obj["code"] in ("W104", "W119"):
                if jshint_error_obj["code"] == "W104":
                    jslint_suffix = " (use 'esversion: 6') or Mozilla JS extensions (use moz)."
                else:
                    jslint_suffix = " (use 'esversion: 6')"

                jshint_error_obj["reason"] = jshint_error_obj["reason"][0: -len(jslint_suffix)-1] +\
                    ". CWL only supports ES5.1"

            jshint_errors.append(jshint_error_obj["code"] + ": " + jshint_error_obj["reason"])

    return jshint_errors, jshint_json.get("globals", [])


def print_js_hint_messages(js_hint_messages, source_line):
    # type: (List[str], SourceLine) -> None
    for js_hint_message in js_hint_messages:
        _logger.warn(source_line.makeError("JSHINT: %s" % js_hint_message))

def validate_js_expressions(tool, schema):
    # type: (CommentedMap, avro.schema.Schema) -> None
    if tool.get("requirements") is None:
        return []

    requirements = tool["requirements"]

    for i, prop in enumerate(reversed(requirements)):
        if prop["class"] == "InlineJavascriptRequirement":
            expression_lib = prop.get("expressionLib", [])
            expression_lib_source_line = SourceLine(requirements, i)
            break
    else:
        return []

    default_globals = ["self", "inputs", "runtime"]

    expression_lib_errors, expression_lib_globals = jshint_js("\n".join(expression_lib), default_globals)
    print_js_hint_messages(expression_lib_errors, expression_lib_source_line)

    expressions = get_expressions(tool, schema)

    for expression, source_line in expressions:
        unscanned_str = expression.strip()
        scan_slice = scan_expression(unscanned_str)

        while scan_slice:
            if unscanned_str[scan_slice[0]] == '$':
                code_fragment = unscanned_str[scan_slice[0] + 1:scan_slice[1]]
                code_fragment_js = code_fragment_to_js(code_fragment, "")
                expression_errors, _ = jshint_js(code_fragment_js, expression_lib_globals + default_globals)
                print_js_hint_messages(expression_errors, source_line)

            unscanned_str = unscanned_str[scan_slice[1]:]
            scan_slice = scan_expression(unscanned_str)
