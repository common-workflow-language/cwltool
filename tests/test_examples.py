import unittest

import cwltool.expression as expr
import cwltool.factory
import cwltool.pathmapper
import cwltool.process
import cwltool.workflow
from .util import get_data
from cwltool.main import main

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
            self.assertNotIn("out2", e.out)
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
            "class": "File",
            "location": "file:///example/bar.cwl"
        },
            {
                "basename": "data.txt",
                "class": "File",
                "location": "file:///example/data.txt"
            },
            {
                "basename": "data2",
                "class": "Directory",
                "location": "file:///example/data2",
                "listing": [{
                    "basename": "data3.txt",
                    "class": "File",
                    "location": "file:///example/data3.txt",
                    "secondaryFiles": [{
                        "class": "File",
                        "basename": "data5.txt",
                        "location": "file:///example/data5.txt"
                    }]
                }]
            }, {
                "basename": "data4.txt",
                "class": "File",
                "location": "file:///example/data4.txt"
            }], sc)

        sc = cwltool.process.scandeps(obj["id"], obj,
                                      set(("run"), ),
                                      set(), loadref)

        sc.sort(key=lambda k: k["basename"])

        self.assertEquals([{
            "basename": "bar.cwl",
            "class": "File",
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

    def test_lifting(self):
        # check that lifting the types of the process outputs to the workflow step
        # fails if the step 'out' doesn't match.
        with self.assertRaises(cwltool.workflow.WorkflowException):
            f = cwltool.factory.Factory()
            echo = f.make(get_data("tests/test_bad_outputs_wf.cwl"))
            self.assertEqual(echo(inp="foo"), {"out": "foo\n"})

class TestPrintDot(unittest.TestCase):
    def test_print_dot(self):
        # Require that --enable-ext is provided.
        self.assertEquals(main(["--print-dot", get_data('tests/wf/revsort.cwl')]), 0)


if __name__ == '__main__':
    unittest.main()
