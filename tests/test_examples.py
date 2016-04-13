import unittest
import json
import cwltool.draft2tool as tool
import cwltool.expression as expr
import cwltool.factory
import cwltool.process


class TestParamMatching(unittest.TestCase):

    def test_params(self):
        self.assertTrue(expr.param_re.match("$(foo)"))
        self.assertTrue(expr.param_re.match("$(foo.bar)"))
        self.assertTrue(expr.param_re.match("$(foo['bar'])"))
        self.assertTrue(expr.param_re.match("$(foo[\"bar\"])"))
        self.assertTrue(expr.param_re.match("$(foo.bar.baz)"))
        self.assertTrue(expr.param_re.match("$(foo['bar'].baz)"))
        self.assertTrue(expr.param_re.match("$(foo['bar']['baz'])"))
        self.assertTrue(expr.param_re.match("$(foo['b\\'ar']['baz'])"))
        self.assertTrue(expr.param_re.match("$(foo['b ar']['baz'])"))
        self.assertTrue(expr.param_re.match("$(foo_bar)"))

        self.assertFalse(expr.param_re.match("$(foo.[\"bar\"])"))
        self.assertFalse(expr.param_re.match("$(.foo[\"bar\"])"))
        self.assertFalse(expr.param_re.match("$(foo [\"bar\"])"))
        self.assertFalse(expr.param_re.match("$( foo[\"bar\"])"))
        self.assertFalse(expr.param_re.match("$(foo[bar].baz)"))
        self.assertFalse(expr.param_re.match("$(foo['bar\"].baz)"))
        self.assertFalse(expr.param_re.match("$(foo['bar].baz)"))
        self.assertFalse(expr.param_re.match("${foo}"))
        self.assertFalse(expr.param_re.match("$(foo.bar"))
        self.assertFalse(expr.param_re.match("$foo.bar)"))
        self.assertFalse(expr.param_re.match("$foo.b ar)"))
        self.assertFalse(expr.param_re.match("$foo.b\'ar)"))
        self.assertFalse(expr.param_re.match("$(foo+bar"))
        self.assertFalse(expr.param_re.match("$(foo bar"))

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
            }
         }

        self.assertEqual(expr.param_interpolate("$(foo)", inputs), inputs["foo"])

        for pattern in ("$(foo.bar)",
                         "$(foo['bar'])",
                         "$(foo[\"bar\"])"):
            self.assertEqual(expr.param_interpolate(pattern, inputs), inputs["foo"]["bar"])

        for pattern in ("$(foo.bar.baz)",
                         "$(foo['bar'].baz)",
                         "$(foo['bar'][\"baz\"])",
                         "$(foo.bar['baz'])"):
            self.assertEqual(expr.param_interpolate(pattern, inputs), "zab1")

        self.assertEqual(expr.param_interpolate("$(foo['b ar'].baz)", inputs), 2)
        self.assertEqual(expr.param_interpolate("$(foo['b\\'ar'].baz)", inputs), True)
        self.assertEqual(expr.param_interpolate("$(foo[\"b'ar\"].baz)", inputs), True)
        self.assertEqual(expr.param_interpolate("$(foo['b\\\"ar'].baz)", inputs), None)


        for pattern in ("-$(foo.bar)",
                         "-$(foo['bar'])",
                         "-$(foo[\"bar\"])"):
            self.assertEqual(expr.param_interpolate(pattern, inputs), """-{"baz": "zab1"}""")

        for pattern in ("-$(foo.bar.baz)",
                         "-$(foo['bar'].baz)",
                         "-$(foo['bar'][\"baz\"])",
                         "-$(foo.bar['baz'])"):
            self.assertEqual(expr.param_interpolate(pattern, inputs), "-zab1")

        self.assertEqual(expr.param_interpolate("-$(foo['b ar'].baz)", inputs), "-2")
        self.assertEqual(expr.param_interpolate("-$(foo['b\\'ar'].baz)", inputs), "-true")
        self.assertEqual(expr.param_interpolate("-$(foo[\"b\\'ar\"].baz)", inputs), "-true")
        self.assertEqual(expr.param_interpolate("-$(foo['b\\\"ar'].baz)", inputs), "-null")


        for pattern in ("$(foo.bar) $(foo.bar)",
                         "$(foo['bar']) $(foo['bar'])",
                         "$(foo[\"bar\"]) $(foo[\"bar\"])"):
            self.assertEqual(expr.param_interpolate(pattern, inputs), """{"baz": "zab1"} {"baz": "zab1"}""")

        for pattern in ("$(foo.bar.baz) $(foo.bar.baz)",
                         "$(foo['bar'].baz) $(foo['bar'].baz)",
                         "$(foo['bar'][\"baz\"]) $(foo['bar'][\"baz\"])",
                         "$(foo.bar['baz']) $(foo.bar['baz'])"):
            self.assertEqual(expr.param_interpolate(pattern, inputs), "zab1 zab1")

        self.assertEqual(expr.param_interpolate("$(foo['b ar'].baz) $(foo['b ar'].baz)", inputs), "2 2")
        self.assertEqual(expr.param_interpolate("$(foo['b\\'ar'].baz) $(foo['b\\'ar'].baz)", inputs), "true true")
        self.assertEqual(expr.param_interpolate("$(foo[\"b\\'ar\"].baz) $(foo[\"b\\'ar\"].baz)", inputs), "true true")
        self.assertEqual(expr.param_interpolate("$(foo['b\\\"ar'].baz) $(foo['b\\\"ar'].baz)", inputs), "null null")

class TestFactory(unittest.TestCase):

    def test_factory(self):
        f = cwltool.factory.Factory()
        echo = f.make("tests/echo.cwl")
        self.assertEqual(echo(inp="foo"), {"out": "foo\n"})

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
                            "path": "file:///example/data.txt"
                        }
                    }],
                    "run": {
                        "id": "file:///example/bar.cwl",
                        "inputs": [{
                            "id": "file:///example/bar.cwl#input2",
                            "default": {
                                "class": "File",
                                "path": "file:///example/data2.txt"
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

        print json.dumps(cwltool.process.scandeps(obj["id"], obj,
                                       set(("$import", "run")),
                                       set(("$include", "$schemas", "path")),
                                                  loadref), indent=4)


if __name__ == '__main__':
    unittest.main()
