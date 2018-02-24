from __future__ import absolute_import
import unittest
import pytest
import subprocess
from os import path
import sys

from io import StringIO

from cwltool.errors import WorkflowException
from cwltool.utils import onWindows

try:
    reload
except:
    try:
        from imp import reload
    except:
        from importlib import reload

import cwltool.expression as expr
import cwltool.factory
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
import schema_salad.validate
from cwltool.main import main

from .util import get_data

sys.argv = ['']

class TestParamMatching(unittest.TestCase):
    def test_params(self):
        self.assertTrue(expr.param_re.match("(foo)"))
        self.assertTrue(expr.param_re.match("(foo.bar)"))
        self.assertTrue(expr.param_re.match("(foo['bar'])"))
        self.assertTrue(expr.param_re.match("(foo[\"bar\"])"))
        self.assertTrue(expr.param_re.match("(foo.bar.baz)"))
        self.assertTrue(expr.param_re.match("(foo['bar'].baz)"))
        self.assertTrue(expr.param_re.match("(foo['bar']['baz'])"))
        self.assertTrue(expr.param_re.match("(foo['b\\'ar']['baz'])"))
        self.assertTrue(expr.param_re.match("(foo['b ar']['baz'])"))
        self.assertTrue(expr.param_re.match("(foo_bar)"))

        self.assertFalse(expr.param_re.match("(foo.[\"bar\"])"))
        self.assertFalse(expr.param_re.match("(.foo[\"bar\"])"))
        self.assertFalse(expr.param_re.match("(foo [\"bar\"])"))
        self.assertFalse(expr.param_re.match("( foo[\"bar\"])"))
        self.assertFalse(expr.param_re.match("(foo[bar].baz)"))
        self.assertFalse(expr.param_re.match("(foo['bar\"].baz)"))
        self.assertFalse(expr.param_re.match("(foo['bar].baz)"))
        self.assertFalse(expr.param_re.match("{foo}"))
        self.assertFalse(expr.param_re.match("(foo.bar"))
        self.assertFalse(expr.param_re.match("foo.bar)"))
        self.assertFalse(expr.param_re.match("foo.b ar)"))
        self.assertFalse(expr.param_re.match("foo.b\'ar)"))
        self.assertFalse(expr.param_re.match("(foo+bar"))
        self.assertFalse(expr.param_re.match("(foo bar"))

        inputs = {
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

        self.assertEqual(expr.interpolate("$(foo)", inputs), inputs["foo"])

        for pattern in ("$(foo.bar)",
                        "$(foo['bar'])",
                        "$(foo[\"bar\"])"):
            self.assertEqual(expr.interpolate(pattern, inputs), inputs["foo"]["bar"])

        for pattern in ("$(foo.bar.baz)",
                        "$(foo['bar'].baz)",
                        "$(foo['bar'][\"baz\"])",
                        "$(foo.bar['baz'])"):
            self.assertEqual(expr.interpolate(pattern, inputs), "zab1")

        self.assertEqual(expr.interpolate("$(foo['b ar'].baz)", inputs), 2)
        self.assertEqual(expr.interpolate("$(foo['b\\'ar'].baz)", inputs), True)
        self.assertEqual(expr.interpolate("$(foo[\"b'ar\"].baz)", inputs), True)
        self.assertEqual(expr.interpolate("$(foo['b\\\"ar'].baz)", inputs), None)

        self.assertEqual(expr.interpolate("$(lst[0])", inputs), "A")
        self.assertEqual(expr.interpolate("$(lst[1])", inputs), "B")
        self.assertEqual(expr.interpolate("$(lst.length)", inputs), 2)
        self.assertEqual(expr.interpolate("$(lst['length'])", inputs), 2)

        for pattern in ("-$(foo.bar)",
                        "-$(foo['bar'])",
                        "-$(foo[\"bar\"])"):
            self.assertEqual(expr.interpolate(pattern, inputs), """-{"baz": "zab1"}""")

        for pattern in ("-$(foo.bar.baz)",
                        "-$(foo['bar'].baz)",
                        "-$(foo['bar'][\"baz\"])",
                        "-$(foo.bar['baz'])"):
            self.assertEqual(expr.interpolate(pattern, inputs), "-zab1")

        self.assertEqual(expr.interpolate("-$(foo['b ar'].baz)", inputs), "-2")
        self.assertEqual(expr.interpolate("-$(foo['b\\'ar'].baz)", inputs), "-true")
        self.assertEqual(expr.interpolate("-$(foo[\"b\\'ar\"].baz)", inputs), "-true")
        self.assertEqual(expr.interpolate("-$(foo['b\\\"ar'].baz)", inputs), "-null")

        for pattern in ("$(foo.bar) $(foo.bar)",
                        "$(foo['bar']) $(foo['bar'])",
                        "$(foo[\"bar\"]) $(foo[\"bar\"])"):
            self.assertEqual(expr.interpolate(pattern, inputs), """{"baz": "zab1"} {"baz": "zab1"}""")

        for pattern in ("$(foo.bar.baz) $(foo.bar.baz)",
                        "$(foo['bar'].baz) $(foo['bar'].baz)",
                        "$(foo['bar'][\"baz\"]) $(foo['bar'][\"baz\"])",
                        "$(foo.bar['baz']) $(foo.bar['baz'])"):
            self.assertEqual(expr.interpolate(pattern, inputs), "zab1 zab1")

        self.assertEqual(expr.interpolate("$(foo['b ar'].baz) $(foo['b ar'].baz)", inputs), "2 2")
        self.assertEqual(expr.interpolate("$(foo['b\\'ar'].baz) $(foo['b\\'ar'].baz)", inputs), "true true")
        self.assertEqual(expr.interpolate("$(foo[\"b\\'ar\"].baz) $(foo[\"b\\'ar\"].baz)", inputs), "true true")
        self.assertEqual(expr.interpolate("$(foo['b\\\"ar'].baz) $(foo['b\\\"ar'].baz)", inputs), "null null")


class TestFactory(unittest.TestCase):
    def test_factory(self):
        f = cwltool.factory.Factory()
        echo = f.make(get_data("tests/echo.cwl"))
        self.assertEqual(echo(inp="foo"), {"out": "foo\n"})

    def test_default_args(self):
        f = cwltool.factory.Factory()
        assert f.execkwargs["use_container"] is True
        assert f.execkwargs["on_error"] == "stop"

    def test_redefined_args(self):
        f = cwltool.factory.Factory(use_container=False, on_error="continue")
        assert f.execkwargs["use_container"] is False
        assert f.execkwargs["on_error"] == "continue"

    def test_partial_scatter(self):
        f = cwltool.factory.Factory(on_error="continue")
        fail = f.make(get_data("tests/wf/scatterfail.cwl"))
        try:
            fail()
        except cwltool.factory.WorkflowStatus as e:
            self.assertEquals('sha1$e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e', e.out["out"][0]["checksum"])
            self.assertIsNone(e.out["out"][1])
            self.assertEquals('sha1$a3db5c13ff90a36963278c6a39e4ee3c22e2a436', e.out["out"][2]["checksum"])
        else:
            self.fail("Should have raised WorkflowStatus")

    def test_partial_output(self):
        f = cwltool.factory.Factory(on_error="continue")
        fail = f.make(get_data("tests/wf/wffail.cwl"))
        try:
            fail()
        except cwltool.factory.WorkflowStatus as e:
            self.assertEquals('sha1$e5fa44f2b31c1fb553b6021e7360d07d5d91ff5e', e.out["out1"]["checksum"])
            self.assertIsNone(e.out["out2"])
        else:
            self.fail("Should have raised WorkflowStatus")


class TestScanDeps(unittest.TestCase):
    def test_scandeps(self):
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
            else:
                raise Exception("test case can't load things")

        sc = cwltool.process.scandeps(obj["id"], obj,
                                      {"$import", "run"},
                                      {"$include", "$schemas", "location"},
                                      loadref)

        sc.sort(key=lambda k: k["basename"])

        self.assertEquals([{
            "basename": "bar.cwl",
            "nameroot": "bar",
            "class": "File",
            "nameext": ".cwl",
            "location": "file:///example/bar.cwl"
        },
            {
                "basename": "data.txt",
                "nameroot": "data",
                "class": "File",
                "nameext": ".txt",
                "location": "file:///example/data.txt"
            },
            {
                "basename": "data2",
                "class": "Directory",
                "location": "file:///example/data2",
                "listing": [{
                    "basename": "data3.txt",
                    "nameroot": "data3",
                    "class": "File",
                    "nameext": ".txt",
                    "location": "file:///example/data3.txt",
                    "secondaryFiles": [{
                        "class": "File",
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
            }], sc)

        sc = cwltool.process.scandeps(obj["id"], obj,
                                      set(("run"), ),
                                      set(), loadref)

        sc.sort(key=lambda k: k["basename"])

        self.assertEquals([{
            "basename": "bar.cwl",
            "nameroot": "bar",
            "class": "File",
            "nameext": ".cwl",
            "location": "file:///example/bar.cwl"
        }], sc)


class TestDedup(unittest.TestCase):
    def test_dedup(self):
        ex = [{
            "class": "File",
            "location": "file:///example/a"
        },
            {
                "class": "File",
                "location": "file:///example/a"
            },
            {
                "class": "File",
                "location": "file:///example/d"
            },
            {
                "class": "Directory",
                "location": "file:///example/c",
                "listing": [{
                    "class": "File",
                    "location": "file:///example/d"
                }]
            }]

        self.assertEquals([{
            "class": "File",
            "location": "file:///example/a"
        },
            {
                "class": "Directory",
                "location": "file:///example/c",
                "listing": [{
                    "class": "File",
                    "location": "file:///example/d"
                }]
            }], cwltool.pathmapper.dedup(ex))


class TestTypeCompare(unittest.TestCase):
    def test_typecompare(self):
        self.assertTrue(cwltool.workflow.can_assign_src_to_sink(
            {'items': ['string', 'null'], 'type': 'array'},
            {'items': ['string', 'null'], 'type': 'array'}))

        self.assertTrue(cwltool.workflow.can_assign_src_to_sink(
            {'items': ['string'], 'type': 'array'},
            {'items': ['string', 'null'], 'type': 'array'}))

        self.assertTrue(cwltool.workflow.can_assign_src_to_sink(
            {'items': ['string', 'null'], 'type': 'array'},
            {'items': ['string'], 'type': 'array'}))

        self.assertFalse(cwltool.workflow.can_assign_src_to_sink(
            {'items': ['string'], 'type': 'array'},
            {'items': ['int'], 'type': 'array'}))

    def test_typecomparestrict(self):
        self.assertTrue(cwltool.workflow.can_assign_src_to_sink(
            ['string', 'null'], ['string', 'null'], strict=True))

        self.assertTrue(cwltool.workflow.can_assign_src_to_sink(
            ['string'], ['string', 'null'], strict=True))

        self.assertFalse(cwltool.workflow.can_assign_src_to_sink(
            ['string', 'int'], ['string', 'null'], strict=True))

        self.assertTrue(cwltool.workflow.can_assign_src_to_sink(
            {'items': ['string'], 'type': 'array'},
            {'items': ['string', 'null'], 'type': 'array'}, strict=True))

        self.assertFalse(cwltool.workflow.can_assign_src_to_sink(
            {'items': ['string', 'int'], 'type': 'array'},
            {'items': ['string', 'null'], 'type': 'array'}, strict=True))

    def test_recordcompare(self):
        src = {
            'fields': [{
                'type': {'items': 'string', 'type': 'array'},
                'name': u'file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/wf-variantcall.cwl#vc_rec/vc_rec/description'
            },
                {
                    'type': {'items': 'File', 'type': 'array'},
                    'name': u'file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/wf-variantcall.cwl#vc_rec/vc_rec/vrn_file'
                }],
            'type': 'record',
            'name': u'file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/wf-variantcall.cwl#vc_rec/vc_rec'
        }
        sink = {
            'fields': [{
                'type': {'items': 'string', 'type': 'array'},
                'name': u'file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/steps/vc_output_record.cwl#vc_rec/vc_rec/description'
            },
                {
                    'type': {'items': 'File', 'type': 'array'},
                    'name': u'file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/steps/vc_output_record.cwl#vc_rec/vc_rec/vrn_file'
                }],
            'type': 'record',
            'name': u'file:///home/chapmanb/drive/work/cwl/test_bcbio_cwl/run_info-cwl-workflow/steps/vc_output_record.cwl#vc_rec/vc_rec'}

        self.assertTrue(cwltool.workflow.can_assign_src_to_sink(src, sink))

        self.assertFalse(cwltool.workflow.can_assign_src_to_sink(src, {'items': 'string', 'type': 'array'}))

    def test_typecheck(self):
        self.assertEquals(cwltool.workflow.check_types(
            ['string', 'int'], ['string', 'int', 'null'], linkMerge=None, valueFrom=None),
            "pass")

        self.assertEquals(cwltool.workflow.check_types(
            ['string', 'int'], ['string', 'null'], linkMerge=None, valueFrom=None),
            "warning")

        self.assertEquals(cwltool.workflow.check_types(
            ['File', 'int'], ['string', 'null'], linkMerge=None, valueFrom=None),
            "exception")

        self.assertEquals(cwltool.workflow.check_types(
            {'items': ['string', 'int'], 'type': 'array'},
            {'items': ['string', 'int', 'null'], 'type': 'array'},
            linkMerge=None, valueFrom=None),
            "pass")

        self.assertEquals(cwltool.workflow.check_types(
            {'items': ['string', 'int'], 'type': 'array'},
            {'items': ['string', 'null'], 'type': 'array'},
            linkMerge=None, valueFrom=None),
            "warning")

        self.assertEquals(cwltool.workflow.check_types(
            {'items': ['File', 'int'], 'type': 'array'},
            {'items': ['string', 'null'], 'type': 'array'},
            linkMerge=None, valueFrom=None),
            "exception")

        # check linkMerge when sinktype is not an array
        self.assertEquals(cwltool.workflow.check_types(
            ['string', 'int'], ['string', 'int', 'null'],
            linkMerge="merge_nested", valueFrom=None),
            "exception")

        # check linkMerge: merge_nested
        self.assertEquals(cwltool.workflow.check_types(
            ['string', 'int'],
            {'items': ['string', 'int', 'null'], 'type': 'array'},
            linkMerge="merge_nested", valueFrom=None),
            "pass")

        self.assertEquals(cwltool.workflow.check_types(
            ['string', 'int'],
            {'items': ['string', 'null'], 'type': 'array'},
            linkMerge="merge_nested", valueFrom=None),
            "warning")

        self.assertEquals(cwltool.workflow.check_types(
            ['File', 'int'],
            {'items': ['string', 'null'], 'type': 'array'},
            linkMerge="merge_nested", valueFrom=None),
            "exception")

        # check linkMerge: merge_nested and sinktype is "Any"
        self.assertEquals(cwltool.workflow.check_types(
            ['string', 'int'], "Any",
            linkMerge="merge_nested", valueFrom=None),
            "pass")

        # check linkMerge: merge_flattened
        self.assertEquals(cwltool.workflow.check_types(
            ['string', 'int'],
            {'items': ['string', 'int', 'null'], 'type': 'array'},
            linkMerge="merge_flattened", valueFrom=None),
            "pass")

        self.assertEquals(cwltool.workflow.check_types(
            ['string', 'int'],
            {'items': ['string', 'null'], 'type': 'array'},
            linkMerge="merge_flattened", valueFrom=None),
            "warning")

        self.assertEquals(cwltool.workflow.check_types(
            ['File', 'int'],
            {'items': ['string', 'null'], 'type': 'array'},
            linkMerge="merge_flattened", valueFrom=None),
            "exception")

        self.assertEquals(cwltool.workflow.check_types(
            {'items': ['string', 'int'], 'type': 'array'},
            {'items': ['string', 'int', 'null'], 'type': 'array'},
            linkMerge="merge_flattened", valueFrom=None),
            "pass")

        self.assertEquals(cwltool.workflow.check_types(
            {'items': ['string', 'int'], 'type': 'array'},
            {'items': ['string', 'null'], 'type': 'array'},
            linkMerge="merge_flattened", valueFrom=None),
            "warning")

        self.assertEquals(cwltool.workflow.check_types(
            {'items': ['File', 'int'], 'type': 'array'},
            {'items': ['string', 'null'], 'type': 'array'},
            linkMerge="merge_flattened", valueFrom=None),
            "exception")

        # check linkMerge: merge_flattened and sinktype is "Any"
        self.assertEquals(cwltool.workflow.check_types(
            ['string', 'int'], "Any",
            linkMerge="merge_flattened", valueFrom=None),
            "pass")

        self.assertEquals(cwltool.workflow.check_types(
            {'items': ['string', 'int'], 'type': 'array'}, "Any",
            linkMerge="merge_flattened", valueFrom=None),
            "pass")

        # check linkMerge: merge_flattened when srctype is a list
        self.assertEquals(cwltool.workflow.check_types(
            [{'items': 'string', 'type': 'array'}],
            {'items': 'string', 'type': 'array'},
            linkMerge="merge_flattened", valueFrom=None),
            "pass")

        # check valueFrom
        self.assertEquals(cwltool.workflow.check_types(
            {'items': ['File', 'int'], 'type': 'array'},
            {'items': ['string', 'null'], 'type': 'array'},
            linkMerge="merge_flattened", valueFrom="special value"),
            "pass")


    def test_lifting(self):
        # check that lifting the types of the process outputs to the workflow step
        # fails if the step 'out' doesn't match.
        with self.assertRaises(schema_salad.validate.ValidationException):
            f = cwltool.factory.Factory()
            echo = f.make(get_data("tests/test_bad_outputs_wf.cwl"))
            self.assertEqual(echo(inp="foo"), {"out": "foo\n"})

    def test_malformed_outputs(self):
        # check that tool validation fails if one of the outputs is not a valid CWL type
        f = cwltool.factory.Factory()
        with self.assertRaises(schema_salad.validate.ValidationException):
            echo = f.make(get_data("tests/wf/malformed_outputs.cwl"))
            echo()

    def test_separate_without_prefix(self):
        # check that setting 'separate = false' on an inputBinding without prefix fails the workflow
        with self.assertRaises(WorkflowException):
            f = cwltool.factory.Factory()
            echo = f.make(get_data("tests/wf/separate_without_prefix.cwl"))
            echo()


    def test_checker(self):
        # check that the static checker raises exception when a source type
        # mismatches its sink type.
        with self.assertRaises(schema_salad.validate.ValidationException):
            f = cwltool.factory.Factory()
            f.make("tests/checker_wf/broken-wf.cwl")
        with self.assertRaises(schema_salad.validate.ValidationException):
            f = cwltool.factory.Factory()
            f.make("tests/checker_wf/broken-wf2.cwl")


class TestPrintDot(unittest.TestCase):
    def test_print_dot(self):
        # Require that --enable-ext is provided.
        self.assertEquals(main(["--print-dot", get_data('tests/wf/revsort.cwl')]), 0)


class TestCmdLine(unittest.TestCase):
    def get_main_output(self, new_args):
        process = subprocess.Popen([
                                       sys.executable,
                                       "-m",
                                       "cwltool"
                                   ] + new_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = process.communicate()
        return process.returncode, stdout.decode(), stderr.decode()


class TestJsConsole(TestCmdLine):

    def test_js_console_cmd_line_tool(self):
        for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
            error_code, stdout, stderr = self.get_main_output(["--js-console", "--no-container",
                                                               get_data("tests/wf/" + test_file)])

            self.assertIn("[log] Log message", stderr)
            self.assertIn("[err] Error message", stderr)

            self.assertEquals(error_code, 0, stderr)

    def test_no_js_console(self):
        for test_file in ("js_output.cwl", "js_output_workflow.cwl"):
            error_code, stdout, stderr = self.get_main_output(["--no-container",
                                                               get_data("tests/wf/" + test_file)])

            self.assertNotIn("[log] Log message", stderr)
            self.assertNotIn("[err] Error message", stderr)


@pytest.mark.skipif(onWindows(),
                    reason="Instance of cwltool is used, on Windows it invokes a default docker container"
                           "which is not supported on AppVeyor")
class TestCache(TestCmdLine):
    def test_wf_without_container(self):
        test_file = "hello-workflow.cwl"
        error_code, stdout, stderr = self.get_main_output(["--cachedir", "cache",
                                                   get_data("tests/wf/" + test_file), "--usermessage", "hello"])
        self.assertIn("completed success", stderr)
        self.assertEquals(error_code, 0)

@pytest.mark.skipif(onWindows(),
                    reason="Instance of cwltool is used, on Windows it invokes a default docker container"
                           "which is not supported on AppVeyor")
class TestChecksum(TestCmdLine):

    def test_compute_checksum(self):
        f = cwltool.factory.Factory(compute_checksum=True, use_container=False)
        echo = f.make(get_data("tests/wf/cat-tool.cwl"))
        output = echo(file1={
                "class": "File",
                "location": get_data("tests/wf/whale.txt")
            },
            reverse=False
        )
        self.assertEquals(output['output']["checksum"], "sha1$327fc7aedf4f6b69a42a7c8b808dc5a7aff61376")

    def test_no_compute_checksum(self):
        test_file = "tests/wf/wc-tool.cwl"
        job_file = "tests/wf/wc-job.json"
        error_code, stdout, stderr = self.get_main_output(["--no-compute-checksum",
                                                   get_data(test_file), get_data(job_file)])
        self.assertIn("completed success", stderr)
        self.assertEquals(error_code, 0)
        self.assertNotIn("checksum", stdout)


if __name__ == '__main__':
    unittest.main()
