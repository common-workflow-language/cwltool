import json
import logging
import os
import shutil
import sys
from io import BytesIO, StringIO
import pytest

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

from .util import (get_data, get_main_output, get_windows_safe_factory, needs_docker,
                   needs_singularity, temp_dir, windows_needs_docker)


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

def test_var_spool_cwl_checker1():
    """ Confirm that references to /var/spool/cwl are caught."""

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
    """ Confirm that references to /var/spool/cwl are caught."""

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
    """ Confirm that references to /var/spool/cwl are caught."""

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

def test_js_console_cmd_line_tool():
    for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
        error_code, _, stderr = get_main_output(
            ["--js-console", "--no-container", get_data("tests/wf/" + test_file)])

        assert "[log] Log message" in stderr
        assert "[err] Error message" in stderr

        assert error_code == 0, stderr

def test_no_js_console():
    for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
        _, _, stderr = get_main_output(
            ["--no-container", get_data("tests/wf/" + test_file)])

        assert "[log] Log message" not in stderr
        assert "[err] Error message" not in stderr

@needs_docker
def test_record_container_id():
    test_file = "cache_test_workflow.cwl"
    with temp_dir('cidr') as cid_dir:
        error_code, _, stderr = get_main_output(
            ["--record-container-id", "--cidfile-dir", cid_dir,
             get_data("tests/wf/" + test_file)])
        assert "completed success" in stderr
        assert error_code == 0
        assert len(os.listdir(cid_dir)) == 2


@needs_docker
def test_wf_without_container():
    test_file = "hello-workflow.cwl"
    with temp_dir("cwltool_cache") as cache_dir:
        error_code, _, stderr = get_main_output(
            ["--cachedir", cache_dir,
             get_data("tests/wf/" + test_file),
             "--usermessage",
             "hello"]
        )

    assert "completed success" in stderr
    assert error_code == 0

@needs_docker
def test_issue_740_fixed():
    test_file = "cache_test_workflow.cwl"
    with temp_dir("cwltool_cache") as cache_dir:
        error_code, _, stderr = get_main_output(
            ["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])

        assert "completed success" in stderr
        assert error_code == 0

        error_code, _, stderr = get_main_output(
            ["--cachedir", cache_dir, get_data("tests/wf/" + test_file)])

        assert "Output of job will be cached in" not in stderr
        assert error_code == 0


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
def test_no_compute_checksum():
    test_file = "tests/wf/wc-tool.cwl"
    job_file = "tests/wf/wc-job.json"
    error_code, stdout, stderr = get_main_output(
        ["--no-compute-checksum", get_data(test_file), get_data(job_file)])
    assert "completed success" in stderr
    assert error_code == 0
    assert "checksum" not in stdout

@needs_singularity
def test_singularity_workflow():
    error_code, _, stderr = get_main_output(
        ['--singularity', '--default-container', 'debian',
         get_data("tests/wf/hello-workflow.cwl"), "--usermessage", "hello"])
    assert "completed success" in stderr
    assert error_code == 0
