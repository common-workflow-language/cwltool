import json
import logging
import os
import stat
import sys
from io import BytesIO, StringIO
import pytest
from typing_extensions import Text

import schema_salad.validate

import cwltool.checker
import cwltool.expression as expr
import cwltool.factory
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
from cwltool.context import RuntimeContext
from cwltool.errors import WorkflowException
from cwltool.main import main
from cwltool.utils import onWindows
from cwltool.resolver import Path
from cwltool.process import CWL_IANA
from cwltool.sandboxjs import JavascriptException
from .util import (get_data, get_main_output, get_windows_safe_factory, subprocess,
                   needs_docker, working_directory, needs_singularity, temp_dir, windows_needs_docker)

import six

try:
    reload
except:  # pylint: disable=bare-except
    try:
        from imp import reload
    except:
        from importlib import reload

sys.argv = ['']

expression_match = [
    ("(foo)", True),
    ("(foo.bar)", True),
    ("(foo['bar'])", True),
    ("(foo[\"bar\"])", True),
    ("(foo.bar.baz)", True),
    ("(foo['bar'].baz)", True),
    ("(foo['bar']['baz'])", True),
    ("(foo['b\\'ar']['baz'])", True),
    ("(foo['b ar']['baz'])", True),
    ("(foo_bar)", True),

    ("(foo.[\"bar\"])", False),
    ("(.foo[\"bar\"])", False),
    ("(foo [\"bar\"])", False),
    ("( foo[\"bar\"])", False),
    ("(foo[bar].baz)", False),
    ("(foo['bar\"].baz)", False),
    ("(foo['bar].baz)", False),
    ("{foo}", False),
    ("(foo.bar", False),
    ("foo.bar)", False),
    ("foo.b ar)", False),
    ("foo.b\'ar)", False),
    ("(foo+bar", False),
    ("(foo bar", False)
]


@pytest.mark.parametrize('expression,expected', expression_match)
def test_expression_match(expression, expected):
    match = expr.param_re.match(expression)
    assert (match is not None) == expected


interpolate_input = {
    "foo": {
        "bar": {
            "baz": "zab1"
        },
        "b ar": {
            "baz": 2
        },
        "b'ar": {
            "baz": True
        },
        'b"ar': {
            "baz": None
        }
    },
    "lst": ["A", "B"]
}

interpolate_parameters = [
    ("$(foo)", interpolate_input["foo"]),

    ("$(foo.bar)", interpolate_input["foo"]["bar"]),
    ("$(foo['bar'])", interpolate_input["foo"]["bar"]),
    ("$(foo[\"bar\"])", interpolate_input["foo"]["bar"]),

    ("$(foo.bar.baz)", interpolate_input['foo']['bar']['baz']),
    ("$(foo['bar'].baz)", interpolate_input['foo']['bar']['baz']),
    ("$(foo['bar'][\"baz\"])", interpolate_input['foo']['bar']['baz']),
    ("$(foo.bar['baz'])", interpolate_input['foo']['bar']['baz']),

    ("$(foo['b\\'ar'].baz)", True),
    ("$(foo[\"b'ar\"].baz)", True),
    ("$(foo['b\\\"ar'].baz)", None),

    ("$(lst[0])", "A"),
    ("$(lst[1])", "B"),
    ("$(lst.length)", 2),
    ("$(lst['length'])", 2),

    ("-$(foo.bar)", """-{"baz": "zab1"}"""),
    ("-$(foo['bar'])", """-{"baz": "zab1"}"""),
    ("-$(foo[\"bar\"])", """-{"baz": "zab1"}"""),

    ("-$(foo.bar.baz)", "-zab1"),
    ("-$(foo['bar'].baz)", "-zab1"),
    ("-$(foo['bar'][\"baz\"])", "-zab1"),
    ("-$(foo.bar['baz'])", "-zab1"),

    ("-$(foo['b ar'].baz)", "-2"),
    ("-$(foo['b\\'ar'].baz)", "-true"),
    ("-$(foo[\"b\\'ar\"].baz)", "-true"),
    ("-$(foo['b\\\"ar'].baz)", "-null"),

    ("$(foo.bar) $(foo.bar)", """{"baz": "zab1"} {"baz": "zab1"}"""),
    ("$(foo['bar']) $(foo['bar'])", """{"baz": "zab1"} {"baz": "zab1"}"""),
    ("$(foo[\"bar\"]) $(foo[\"bar\"])", """{"baz": "zab1"} {"baz": "zab1"}"""),

    ("$(foo.bar.baz) $(foo.bar.baz)", "zab1 zab1"),
    ("$(foo['bar'].baz) $(foo['bar'].baz)", "zab1 zab1"),
    ("$(foo['bar'][\"baz\"]) $(foo['bar'][\"baz\"])", "zab1 zab1"),
    ("$(foo.bar['baz']) $(foo.bar['baz'])", "zab1 zab1"),

    ("$(foo['b ar'].baz) $(foo['b ar'].baz)", "2 2"),
    ("$(foo['b\\'ar'].baz) $(foo['b\\'ar'].baz)", "true true"),
    ("$(foo[\"b\\'ar\"].baz) $(foo[\"b\\'ar\"].baz)", "true true"),
    ("$(foo['b\\\"ar'].baz) $(foo['b\\\"ar'].baz)", "null null")
]


@pytest.mark.parametrize('pattern,expected', interpolate_parameters)
def test_expression_interpolate(pattern, expected):
    assert expr.interpolate(pattern, interpolate_input) == expected

interpolate_bad_parameters = [
    ("$(fooz)"),
    ("$(foo.barz)"),
    ("$(foo['barz'])"),
    ("$(foo[\"barz\"])"),

    ("$(foo.bar.bazz)"),
    ("$(foo['bar'].bazz)"),
    ("$(foo['bar'][\"bazz\"])"),
    ("$(foo.bar['bazz'])"),

    ("$(foo['b\\'ar'].bazz)"),
    ("$(foo[\"b'ar\"].bazz)"),
    ("$(foo['b\\\"ar'].bazz)"),

    ("$(lst[O])"),  # not "0" the number, but the letter O
    ("$(lst[2])"),
    ("$(lst.lengthz)"),
    ("$(lst['lengthz'])"),

    ("-$(foo.barz)"),
    ("-$(foo['barz'])"),
    ("-$(foo[\"barz\"])"),

    ("-$(foo.bar.bazz)"),
    ("-$(foo['bar'].bazz)"),
    ("-$(foo['bar'][\"bazz\"])"),
    ("-$(foo.bar['bazz'])"),

    ("-$(foo['b ar'].bazz)"),
    ("-$(foo['b\\'ar'].bazz)"),
    ("-$(foo[\"b\\'ar\"].bazz)"),
    ("-$(foo['b\\\"ar'].bazz)"),
]

@pytest.mark.parametrize('pattern', interpolate_bad_parameters)
def test_expression_interpolate_failures(pattern):
    result = None
    try:
        result = expr.interpolate(pattern, interpolate_input)
    except JavascriptException:
        return
    assert false, 'Should have produced a JavascriptException, got "{}".'.format(result)


@windows_needs_docker
def test_factory():
    factory = get_windows_safe_factory()
    echo = factory.make(get_data("tests/echo.cwl"))

    assert echo(inp="foo") == {"out": "foo\n"}


def test_factory_bad_outputs():
    factory = cwltool.factory.Factory()

    with pytest.raises(schema_salad.validate.ValidationException):
        factory.make(get_data("tests/echo_broken_outputs.cwl"))


def test_factory_default_args():
    factory = cwltool.factory.Factory()

    assert factory.runtime_context.use_container is True
    assert factory.runtime_context.on_error == "stop"


def test_factory_redefined_args():
    runtime_context = RuntimeContext()
    runtime_context.use_container = False
    runtime_context.on_error = "continue"
    factory = cwltool.factory.Factory(runtime_context=runtime_context)

    assert factory.runtime_context.use_container is False
    assert factory.runtime_context.on_error == "continue"


def test_factory_partial_scatter():
    runtime_context = RuntimeContext()
    runtime_context.on_error = "continue"
    factory = cwltool.factory.Factory(runtime_context=runtime_context)

    with pytest.raises(cwltool.factory.WorkflowStatus) as err_info:
        factory.make(get_data("tests/wf/scatterfail.cwl"))()

    err = err_info.value
    assert err.out["out"][0]["checksum"] == 'sha1$e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e'
    assert err.out["out"][1] is None
    assert err.out["out"][2]["checksum"] == 'sha1$a3db5c13ff90a36963278c6a39e4ee3c22e2a436'


def test_factory_partial_output():
    runtime_context = RuntimeContext()
    runtime_context.on_error = "continue"
    factory = cwltool.factory.Factory(runtime_context=runtime_context)

    with pytest.raises(cwltool.factory.WorkflowStatus) as err_info:
        factory.make(get_data("tests/wf/wffail.cwl"))()

    err = err_info.value
    assert err.out["out1"]["checksum"] == 'sha1$e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e'
    assert err.out["out2"] is None


def test_scandeps():
    obj = {
        "id": "file:///example/foo.cwl",
        "steps": [
            {
                "id": "file:///example/foo.cwl#step1",
                "inputs": [{
                    "id": "file:///example/foo.cwl#input1",
                    "default": {
                        "class": "File",
                        "location": "file:///example/data.txt"
                    }
                }],
                "run": {
                    "id": "file:///example/bar.cwl",
                    "inputs": [{
                        "id": "file:///example/bar.cwl#input2",
                        "default": {
                            "class": "Directory",
                            "location": "file:///example/data2",
                            "listing": [{
                                "class": "File",
                                "location": "file:///example/data3.txt",
                                "secondaryFiles": [{
                                    "class": "File",
                                    "location": "file:///example/data5.txt"
                                }]
                            }]
                        },
                    }, {
                        "id": "file:///example/bar.cwl#input3",
                        "default": {
                            "class": "Directory",
                            "listing": [{
                                "class": "File",
                                "location": "file:///example/data4.txt"
                            }]
                        }
                    }, {
                        "id": "file:///example/bar.cwl#input4",
                        "default": {
                            "class": "File",
                            "contents": "file literal"
                        }
                    }]
                }
            }
        ]
    }

    def loadref(base, p):
        if isinstance(p, dict):
            return p
        raise Exception("test case can't load things")

    scanned_deps = cwltool.process.scandeps(
        obj["id"], obj,
        {"$import", "run"},
        {"$include", "$schemas", "location"},
        loadref)

    scanned_deps.sort(key=lambda k: k["basename"])

    expected_deps = [
        {"basename": "bar.cwl",
         "nameroot": "bar",
         "class": "File",
         "format": CWL_IANA,
         "nameext": ".cwl",
         "location": "file:///example/bar.cwl"},
        {"basename": "data.txt",
         "nameroot": "data",
         "class": "File",
         "nameext": ".txt",
         "location": "file:///example/data.txt"},
        {"basename": "data2",
         "class": "Directory",
         "location": "file:///example/data2",
         "listing": [
             {"basename": "data3.txt",
              "nameroot": "data3",
              "class": "File",
              "nameext": ".txt",
              "location": "file:///example/data3.txt",
              "secondaryFiles": [
                  {"class": "File",
                   "basename": "data5.txt",
                   "location": "file:///example/data5.txt",
                   "nameext": ".txt",
                   "nameroot": "data5"
                   }]
              }]
         }, {
            "basename": "data4.txt",
            "nameroot": "data4",
            "class": "File",
            "nameext": ".txt",
            "location": "file:///example/data4.txt"
        }]

    assert scanned_deps == expected_deps

    scanned_deps = cwltool.process.scandeps(
        obj["id"], obj,
        set(("run"), ),
        set(), loadref)

    scanned_deps.sort(key=lambda k: k["basename"])

    expected_deps = [{
        "basename": "bar.cwl",
        "nameroot": "bar",
        "format": CWL_IANA,
        "class": "File",
        "nameext": ".cwl",
        "location": "file:///example/bar.cwl"
    }]

    assert scanned_deps == expected_deps

def test_trick_scandeps():
    if sys.version_info[0] < 3:
        stream = BytesIO()
    else:
        stream = StringIO()

    main(["--print-deps", "--debug", get_data("tests/wf/trick_defaults.cwl")], stdout=stream)
    assert json.loads(stream.getvalue())["secondaryFiles"][0]["location"][:2] != "_:"


def test_input_deps():
    if sys.version_info[0] < 3:
        stream = BytesIO()
    else:
        stream = StringIO()

    main(["--print-input-deps", get_data("tests/wf/count-lines1-wf.cwl"),
          get_data("tests/wf/wc-job.json")], stdout=stream)

    expected = {"class": "File",
                "location": "wc-job.json",
                "format": CWL_IANA,
                "secondaryFiles": [{"class": "File",
                                    "location": "whale.txt",
                                    "basename": "whale.txt",
                                    "nameroot": "whale",
                                    "nameext": ".txt"}]}
    assert json.loads(stream.getvalue()) == expected


def test_input_deps_cmdline_opts():
    if sys.version_info[0] < 3:
        stream = BytesIO()
    else:
        stream = StringIO()

    main(["--print-input-deps",
          get_data("tests/wf/count-lines1-wf.cwl"),
          "--file1", get_data("tests/wf/whale.txt")], stdout=stream)
    expected = {"class": "File",
                "location": "",
                "format": CWL_IANA,
                "secondaryFiles": [{"class": "File",
                                    "location": "whale.txt",
                                    "basename": "whale.txt",
                                    "nameroot": "whale",
                                    "nameext": ".txt"}]}
    assert json.loads(stream.getvalue()) == expected


def test_input_deps_cmdline_opts_relative_deps_cwd():
    if sys.version_info[0] < 3:
        stream = BytesIO()
    else:
        stream = StringIO()

    data_path = get_data("tests/wf/whale.txt")
    main(["--print-input-deps", "--relative-deps", "cwd",
          get_data("tests/wf/count-lines1-wf.cwl"),
          "--file1", data_path], stdout=stream)

    goal = {"class": "File",
            "location": "",
            "format": CWL_IANA,
            "secondaryFiles": [{"class": "File",
                                "location": str(
                                    Path(os.path.relpath(
                                        data_path, os.path.curdir))),
                                "basename": "whale.txt",
                                "nameroot": "whale",
                                "nameext": ".txt"}]}
    assert json.loads(stream.getvalue()) == goal


def test_dedupe():
    not_deduped = [
        {"class": "File",
         "location": "file:///example/a"},
        {"class": "File",
         "location": "file:///example/a"},
        {"class": "File",
         "location": "file:///example/d"},
        {"class": "Directory",
         "location": "file:///example/c",
         "listing": [
             {"class": "File",
              "location": "file:///example/d"}
         ]}
    ]

    expected = [
        {"class": "File",
         "location": "file:///example/a"},
        {"class": "Directory",
         "location": "file:///example/c",
         "listing": [
             {"class": "File",
              "location": "file:///example/d"}
         ]}
    ]

    assert cwltool.pathmapper.dedup(not_deduped) == expected


record = {
    'fields': [
        {'type': {'items': 'string', 'type': 'array'},
         'name': u'file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/wf-variantcall.cwl#vc_rec/vc_rec/description'
         },
        {'type': {'items': 'File', 'type': 'array'},
         'name': u'file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/wf-variantcall.cwl#vc_rec/vc_rec/vrn_file'
         }],
    'type': 'record',
    'name': u'file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/wf-variantcall.cwl#vc_rec/vc_rec'
}

source_to_sink = [
    ('0',
     {'items': ['string', 'null'], 'type': 'array'},
     {'items': ['string', 'null'], 'type': 'array'},
     True
     ),
    ('1',
     {'items': ['string'], 'type': 'array'},
     {'items': ['string', 'null'], 'type': 'array'},
     True
     ),
    ('2',
     {'items': ['string', 'null'], 'type': 'array'},
     {'items': ['string'], 'type': 'array'},
     True
     ),
    ('3',
     {'items': ['string'], 'type': 'array'},
     {'items': ['int'], 'type': 'array'},
     False
     ),
    ('record 0',
     record, record,
     True
     ),
    ('record 1',
     record, {'items': 'string', 'type': 'array'},
     False
     )
]


@pytest.mark.parametrize('name, source, sink, expected', source_to_sink)
def test_compare_types(name, source, sink, expected):
    assert cwltool.workflow.can_assign_src_to_sink(source, sink) == expected, name


source_to_sink_strict = [
    ('0',
     ['string', 'null'], ['string', 'null'],
     True
     ),
    ('1',
     ['string'], ['string', 'null'],
     True
     ),
    ('2',
     ['string', 'int'], ['string', 'null'],
     False
     ),
    ('3',
     {'items': ['string'], 'type': 'array'},
     {'items': ['string', 'null'], 'type': 'array'},
     True
     ),
    ('4',
     {'items': ['string', 'int'], 'type': 'array'},
     {'items': ['string', 'null'], 'type': 'array'},
     False
     )
]


@pytest.mark.parametrize('name, source, sink, expected', source_to_sink_strict)
def test_compare_types_strict(name, source, sink, expected):
    assert cwltool.workflow.can_assign_src_to_sink(source, sink, strict=True) == expected, name


typechecks = [
    (['string', 'int'], ['string', 'int', 'null'],
     None, None,
     "pass"
     ),
    (['string', 'int'], ['string', 'null'],
     None, None,
     "warning"
     ),
    (['File', 'int'], ['string', 'null'],
     None, None,
     "exception"
     ),
    ({'items': ['string', 'int'], 'type': 'array'},
     {'items': ['string', 'int', 'null'], 'type': 'array'},
     None, None,
     "pass"
     ),
    ({'items': ['string', 'int'], 'type': 'array'},
     {'items': ['string', 'null'], 'type': 'array'},
     None, None,
     "warning"
     ),
    ({'items': ['File', 'int'], 'type': 'array'},
     {'items': ['string', 'null'], 'type': 'array'},
     None, None,
     "exception"
     ),
    # check linkMerge when sinktype is not an array
    (['string', 'int'], ['string', 'int', 'null'],
     "merge_nested", None,
     "exception"
     ),
    # check linkMerge: merge_nested
    (['string', 'int'],
     {'items': ['string', 'int', 'null'], 'type': 'array'},
     "merge_nested", None,
     "pass"
     ),
    (['string', 'int'],
     {'items': ['string', 'null'], 'type': 'array'},
     "merge_nested", None,
     "warning"
     ),
    (['File', 'int'],
     {'items': ['string', 'null'], 'type': 'array'},
     "merge_nested", None,
     "exception"
     ),
    # check linkMerge: merge_nested and sinktype is "Any"
    (['string', 'int'], "Any",
     "merge_nested", None,
     "pass"
     ),
    # check linkMerge: merge_flattened
    (['string', 'int'],
     {'items': ['string', 'int', 'null'], 'type': 'array'},
     "merge_flattened", None,
     "pass"
     ),
    (['string', 'int'],
     {'items': ['string', 'null'], 'type': 'array'},
     "merge_flattened", None,
     "warning"
     ),
    (['File', 'int'],
     {'items': ['string', 'null'], 'type': 'array'},
     "merge_flattened", None,
     "exception"
     ),
    ({'items': ['string', 'int'], 'type': 'array'},
     {'items': ['string', 'int', 'null'], 'type': 'array'},
     "merge_flattened", None,
     "pass"
     ),
    ({'items': ['string', 'int'], 'type': 'array'},
     {'items': ['string', 'null'], 'type': 'array'},
     "merge_flattened", None,
     "warning"
     ),
    ({'items': ['File', 'int'], 'type': 'array'},
     {'items': ['string', 'null'], 'type': 'array'},
     "merge_flattened", None,
     "exception"),
    # check linkMerge: merge_flattened and sinktype is "Any"
    (['string', 'int'], "Any",
     "merge_flattened", None,
     "pass"
     ),
    ({'items': ['string', 'int'], 'type': 'array'}, "Any",
     "merge_flattened", None,
     "pass"
     ),
    # check linkMerge: merge_flattened when srctype is a list
    ([{'items': 'string', 'type': 'array'}],
     {'items': 'string', 'type': 'array'},
     "merge_flattened", None,
     "pass"
     ),
    # check valueFrom
    ({'items': ['File', 'int'], 'type': 'array'},
     {'items': ['string', 'null'], 'type': 'array'},
     "merge_flattened", "special value",
     "pass"
     )
]


@pytest.mark.parametrize('src_type,sink_type,link_merge,value_from,expected_type', typechecks)
def test_typechecking(src_type, sink_type, link_merge, value_from, expected_type):
    assert cwltool.checker.check_types(
        src_type, sink_type, linkMerge=link_merge, valueFrom=value_from
    ) == expected_type


def test_lifting():
    # check that lifting the types of the process outputs to the workflow step
    # fails if the step 'out' doesn't match.
    factory = cwltool.factory.Factory()
    with pytest.raises(schema_salad.validate.ValidationException):
        echo = factory.make(get_data("tests/test_bad_outputs_wf.cwl"))
        assert echo(inp="foo") == {"out": "foo\n"}


def test_malformed_outputs():
    # check that tool validation fails if one of the outputs is not a valid CWL type
    factory = cwltool.factory.Factory()
    with pytest.raises(schema_salad.validate.ValidationException):
        factory.make(get_data("tests/wf/malformed_outputs.cwl"))()


def test_separate_without_prefix():
    # check that setting 'separate = false' on an inputBinding without prefix fails the workflow
    factory = cwltool.factory.Factory()
    with pytest.raises(WorkflowException):
        factory.make(get_data("tests/wf/separate_without_prefix.cwl"))()


def test_static_checker():
    # check that the static checker raises exception when a source type
    # mismatches its sink type.
    factory = cwltool.factory.Factory()

    with pytest.raises(schema_salad.validate.ValidationException):
        factory.make(get_data("tests/checker_wf/broken-wf.cwl"))

    with pytest.raises(schema_salad.validate.ValidationException):
        factory.make(get_data("tests/checker_wf/broken-wf2.cwl"))

    with pytest.raises(schema_salad.validate.ValidationException):
        factory.make(get_data("tests/checker_wf/broken-wf3.cwl"))


def test_var_spool_cwl_checker1():
    """Confirm that references to /var/spool/cwl are caught."""
    stream = StringIO()
    streamhandler = logging.StreamHandler(stream)
    _logger = logging.getLogger("cwltool")
    _logger.addHandler(streamhandler)

    factory = cwltool.factory.Factory()
    try:
        factory.make(get_data("tests/non_portable.cwl"))
        assert "non_portable.cwl:18:4: Non-portable reference to /var/spool/cwl detected" in stream.getvalue()
    finally:
        _logger.removeHandler(streamhandler)


def test_var_spool_cwl_checker2():
    """Confirm that references to /var/spool/cwl are caught."""
    stream = StringIO()
    streamhandler = logging.StreamHandler(stream)
    _logger = logging.getLogger("cwltool")
    _logger.addHandler(streamhandler)

    factory = cwltool.factory.Factory()
    try:
        factory.make(get_data("tests/non_portable2.cwl"))
        assert "non_portable2.cwl:19:4: Non-portable reference to /var/spool/cwl detected" in stream.getvalue()
    finally:
        _logger.removeHandler(streamhandler)


def test_var_spool_cwl_checker3():
    """Confirm that references to /var/spool/cwl are caught."""
    stream = StringIO()
    streamhandler = logging.StreamHandler(stream)
    _logger = logging.getLogger("cwltool")
    _logger.addHandler(streamhandler)

    factory = cwltool.factory.Factory()
    try:
        factory.make(get_data("tests/portable.cwl"))
        assert "Non-portable reference to /var/spool/cwl detected" not in stream.getvalue()
    finally:
        _logger.removeHandler(streamhandler)


def test_print_dot():
    assert main(["--print-dot", get_data('tests/wf/revsort.cwl')]) == 0

test_factors = [(""), ("--parallel"), ("--debug"), ("--parallel --debug")]

@pytest.mark.parametrize("factor", test_factors)
def test_js_console_cmd_line_tool(factor):
    for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
        commands = factor.split()
        commands.extend(["--js-console", "--no-container", get_data("tests/wf/" + test_file)])
        error_code, _, stderr = get_main_output(commands)

        assert "[log] Log message" in stderr
        assert "[err] Error message" in stderr

        assert error_code == 0, stderr

@pytest.mark.parametrize("factor", test_factors)
def test_no_js_console(factor):
    for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
        commands = factor.split()
        commands.extend(["--no-container", get_data("tests/wf/" + test_file)])
        _, _, stderr = get_main_output(commands)

        assert "[log] Log message" not in stderr
        assert "[err] Error message" not in stderr


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cid_file_dir(tmpdir, factor):
    test_file = "cache_test_workflow.cwl"
    cwd = tmpdir.chdir()
    commands = factor.split()
    commands.extend(["--cidfile-dir", str(tmpdir), get_data("tests/wf/" + test_file)])
    error_code, stdout, stderr = get_main_output(commands)
    assert "completed success" in stderr
    assert error_code == 0
    cidfiles_count = sum(1 for _ in tmpdir.visit(fil="*"))
    assert cidfiles_count == 2
    cwd.chdir()
    tmpdir.remove(ignore_errors=True)


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cid_file_dir_arg_is_file_instead_of_dir(tmpdir, factor):
    test_file = "cache_test_workflow.cwl"
    bad_cidfile_dir = Text(tmpdir.ensure("cidfile-dir-actually-a-file"))
    commands = factor.split()
    commands.extend(["--cidfile-dir", bad_cidfile_dir,
         get_data("tests/wf/" + test_file)])
    error_code, _, stderr = get_main_output(commands)
    assert "is not a directory, please check it first" in stderr, stderr
    assert error_code == 2 or error_code == 1, stderr
    tmpdir.remove(ignore_errors=True)


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cid_file_non_existing_dir(tmpdir, factor):
    test_file = "cache_test_workflow.cwl"
    bad_cidfile_dir = Text(tmpdir.join("cidfile-dir-badpath"))
    commands = factor.split()
    commands.extend(['--record-container-id',"--cidfile-dir", bad_cidfile_dir,
         get_data("tests/wf/" + test_file)])
    error_code, _, stderr = get_main_output(commands)
    assert "directory doesn't exist, please create it first" in stderr, stderr
    assert error_code == 2 or error_code == 1, stderr
    tmpdir.remove(ignore_errors=True)


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_cid_file_w_prefix(tmpdir, factor):
    test_file = "cache_test_workflow.cwl"
    cwd = tmpdir.chdir()
    try:
        commands = factor.split()
        commands.extend(['--record-container-id', '--cidfile-prefix=pytestcid',
             get_data("tests/wf/" + test_file)])
        error_code, stdout, stderr = get_main_output(commands)
    finally:
        listing = tmpdir.listdir()
        cwd.chdir()
        cidfiles_count = sum(1 for _ in tmpdir.visit(fil="pytestcid*"))
        tmpdir.remove(ignore_errors=True)
    assert "completed success" in stderr
    assert error_code == 0
    assert cidfiles_count == 2, '{}/n{}'.format(listing, stderr)


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_secondary_files_v1_1(factor):
    test_file = "secondary-files.cwl"
    test_job_file = "secondary-files-job.yml"
    try:
        old_umask = os.umask(stat.S_IWOTH)  # test run with umask 002
        commands = factor.split()
        commands.extend(["--enable-dev",
            get_data(os.path.join("tests", test_file)),
            get_data(os.path.join("tests", test_job_file))])
        error_code, _, stderr = get_main_output(commands)
    finally:
        assert stat.S_IMODE(os.stat('lsout').st_mode) == 436  # 664 in octal, '-rw-rw-r--'
        os.umask(old_umask)  # revert back to original umask
    assert "completed success" in stderr
    assert error_code == 0

@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_secondary_files_v1_0(factor):
    test_file = "secondary-files-string-v1.cwl"
    test_job_file = "secondary-files-job.yml"
    try:
        old_umask = os.umask(stat.S_IWOTH)  # test run with umask 002
        commands = factor.split()
        commands.extend([
                get_data(os.path.join("tests", test_file)),
                get_data(os.path.join("tests", test_job_file))
            ])
        error_code, _, stderr = get_main_output(commands)
    finally:
        assert stat.S_IMODE(os.stat('lsout').st_mode) == 436  # 664 in octal, '-rw-rw-r--'
        os.umask(old_umask)  # revert back to original umask
    assert "completed success" in stderr
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_wf_without_container(tmpdir, factor):
    test_file = "hello-workflow.cwl"
    with temp_dir("cwltool_cache") as cache_dir:
        commands = factor.split()
        commands.extend(["--cachedir", cache_dir, "--outdir", str(tmpdir),
             get_data("tests/wf/" + test_file),
             "--usermessage",
             "hello"])
        error_code, _, stderr = get_main_output(commands)

    assert "completed success" in stderr
    assert error_code == 0


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_issue_740_fixed(factor):
    test_file = "cache_test_workflow.cwl"
    with temp_dir("cwltool_cache") as cache_dir:
        commands = factor.split()
        commands.extend(["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])
        error_code, _, stderr = get_main_output(commands)

        assert "completed success" in stderr
        assert error_code == 0

        commands = factor.split()
        commands.extend(["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])
        error_code, _, stderr = get_main_output(commands)

        assert "Output of job will be cached in" not in stderr
        assert error_code == 0, stderr


@needs_docker
def test_compute_checksum():
    runtime_context = RuntimeContext()
    runtime_context.compute_checksum = True
    runtime_context.use_container = onWindows()
    factory = cwltool.factory.Factory(runtime_context=runtime_context)
    echo = factory.make(get_data("tests/wf/cat-tool.cwl"))
    output = echo(
        file1={"class": "File",
               "location": get_data("tests/wf/whale.txt")},
        reverse=False)
    assert output['output']["checksum"] == "sha1$327fc7aedf4f6b69a42a7c8b808dc5a7aff61376"


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_no_compute_chcksum(tmpdir, factor):
    test_file = "tests/wf/wc-tool.cwl"
    job_file = "tests/wf/wc-job.json"
    commands = factor.split()
    commands.extend(["--no-compute-checksum", "--outdir", str(tmpdir),
         get_data(test_file), get_data(job_file)])
    error_code, stdout, stderr = get_main_output(commands)
    assert "completed success" in stderr
    assert error_code == 0
    assert "checksum" not in stdout


@pytest.mark.parametrize("factor", test_factors)
def test_bad_userspace_runtime(factor):
    test_file = "tests/wf/wc-tool.cwl"
    job_file = "tests/wf/wc-job.json"
    commands = factor.split()
    commands.extend([
        "--user-space-docker-cmd=quaquioN", "--default-container=debian",
        get_data(test_file), get_data(job_file)])
    error_code, stdout, stderr = get_main_output(commands)
    assert "or quaquioN is missing or broken" in stderr, stderr
    assert error_code == 1

@windows_needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_bad_basecommand(factor):
    test_file = "tests/wf/missing-tool.cwl"
    commands = factor.split()
    commands.extend([get_data(test_file)])
    error_code, stdout, stderr = get_main_output(commands)
    assert "'neenooGo' not found" in stderr, stderr
    assert error_code == 1


@needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_bad_basecommand_docker(factor):
    test_file = "tests/wf/missing-tool.cwl"
    commands = factor.split()
    commands.extend(
        ["--debug", "--default-container", "debian", get_data(test_file)])
    error_code, stdout, stderr = get_main_output(commands)
    assert "permanentFail" in stderr, stderr
    assert error_code == 1

@pytest.mark.parametrize("factor", test_factors)
def test_v1_0_position_expression(factor):
    test_file = "tests/echo-position-expr.cwl"
    test_job = "tests/echo-position-expr-job.yml"
    commands = factor.split()
    commands.extend(
        ['--debug', get_data(test_file), get_data(test_job)])
    error_code, stdout, stderr = get_main_output(commands)
    assert "is not int" in stderr, stderr
    assert error_code == 1


@windows_needs_docker
@pytest.mark.parametrize("factor", test_factors)
def test_optional_numeric_output_0(factor):
    test_file = "tests/wf/optional-numerical-output-0.cwl"
    commands = factor.split()
    commands.extend([get_data(test_file)])
    error_code, stdout, stderr = get_main_output(commands)

    assert "completed success" in stderr
    assert error_code == 0
    assert json.loads(stdout)['out'] == 0

@pytest.mark.parametrize("factor", test_factors)
@windows_needs_docker
def test_env_filtering(factor):
    test_file = "tests/env.cwl"
    commands = factor.split()
    commands.extend([get_data(test_file)])
    error_code, stdout, stderr = get_main_output(commands)

    process = subprocess.Popen(["sh", "-c", r"""getTrueShellExeName() {
  local trueExe nextTarget 2>/dev/null
  trueExe=$(ps -o comm= $$) || return 1
  [ "${trueExe#-}" = "$trueExe" ] || trueExe=${trueExe#-}
  [ "${trueExe#/}" != "$trueExe" ] || trueExe=$([ -n "$ZSH_VERSION" ] && which -p "$trueExe" || which "$trueExe")
  while nextTarget=$(readlink "$trueExe"); do trueExe=$nextTarget; done
  printf '%s\n' "$(basename "$trueExe")"
} ; getTrueShellExeName"""], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=None)
    sh_name, sh_name_err = process.communicate()
    sh_name = sh_name.decode('utf-8').strip()

    assert "completed success" in stderr, (error_code, stdout, stderr)
    assert error_code == 0, (error_code, stdout, stderr)
    if onWindows():
        target = 5
    elif sh_name == "dash":
        target = 4
    else:  # bash adds "SHLVL" and "_" environment variables
        target = 6
    result = json.loads(stdout)['env_count']
    details = ''
    if result != target:
        _, details, _ = get_main_output(["--quiet", get_data("tests/env2.cwl")])
        print(sh_name)
        print(sh_name_err)
        print(details)
    assert result == target, (error_code, sh_name, sh_name_err, details, stdout, stderr)

@windows_needs_docker
def test_v1_0_arg_empty_prefix_separate_false():
    test_file = "tests/arg-empty-prefix-separate-false.cwl"
    error_code, stdout, stderr = get_main_output(
        ['--debug', get_data(test_file), "--echo"])
    assert "completed success" in stderr
    assert error_code == 0
