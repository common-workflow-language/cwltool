import unittest
import cwltool.draft2tool as tool
import cwltool.expression as expr
import cwltool.factory


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

        self.assertEqual(
            expr.param_interpolate("$(foo)", inputs), inputs["foo"])

        for pattern in ("$(foo.bar)",
                        "$(foo['bar'])",
                        "$(foo[\"bar\"])"):
            self.assertEqual(expr.param_interpolate(
                pattern, inputs), inputs["foo"]["bar"])

        for pattern in ("$(foo.bar.baz)",
                        "$(foo['bar'].baz)",
                        "$(foo['bar'][\"baz\"])",
                        "$(foo.bar['baz'])"):
            self.assertEqual(expr.param_interpolate(pattern, inputs), "zab1")

        self.assertEqual(
            expr.param_interpolate("$(foo['b ar'].baz)", inputs), 2)
        self.assertEqual(expr.param_interpolate(
            "$(foo['b\\'ar'].baz)", inputs), True)
        self.assertEqual(expr.param_interpolate(
            "$(foo[\"b'ar\"].baz)", inputs), True)
        self.assertEqual(expr.param_interpolate(
            "$(foo['b\\\"ar'].baz)", inputs), None)

        for pattern in ("-$(foo.bar)",
                        "-$(foo['bar'])",
                        "-$(foo[\"bar\"])"):
            self.assertEqual(expr.param_interpolate(
                pattern, inputs), """-{"baz": "zab1"}""")

        for pattern in ("-$(foo.bar.baz)",
                        "-$(foo['bar'].baz)",
                        "-$(foo['bar'][\"baz\"])",
                        "-$(foo.bar['baz'])"):
            self.assertEqual(expr.param_interpolate(pattern, inputs), "-zab1")

        self.assertEqual(
            expr.param_interpolate("-$(foo['b ar'].baz)", inputs), "-2")
        self.assertEqual(expr.param_interpolate(
            "-$(foo['b\\'ar'].baz)", inputs), "-true")
        self.assertEqual(expr.param_interpolate(
            "-$(foo[\"b\\'ar\"].baz)", inputs), "-true")
        self.assertEqual(expr.param_interpolate(
            "-$(foo['b\\\"ar'].baz)", inputs), "-null")

        for pattern in ("$(foo.bar) $(foo.bar)",
                        "$(foo['bar']) $(foo['bar'])",
                        "$(foo[\"bar\"]) $(foo[\"bar\"])"):
            self.assertEqual(expr.param_interpolate(
                pattern, inputs), """{"baz": "zab1"} {"baz": "zab1"}""")

        for pattern in ("$(foo.bar.baz) $(foo.bar.baz)",
                        "$(foo['bar'].baz) $(foo['bar'].baz)",
                        "$(foo['bar'][\"baz\"]) $(foo['bar'][\"baz\"])",
                        "$(foo.bar['baz']) $(foo.bar['baz'])"):
            self.assertEqual(
                expr.param_interpolate(pattern, inputs), "zab1 zab1")

        self.assertEqual(expr.param_interpolate(
            "$(foo['b ar'].baz) $(foo['b ar'].baz)", inputs), "2 2")
        self.assertEqual(expr.param_interpolate(
            "$(foo['b\\'ar'].baz) $(foo['b\\'ar'].baz)", inputs), "true true")
        self.assertEqual(expr.param_interpolate(
            "$(foo[\"b\\'ar\"].baz) $(foo[\"b\\'ar\"].baz)", inputs),
            "true true")
        self.assertEqual(expr.param_interpolate(
            "$(foo['b\\\"ar'].baz) $(foo['b\\\"ar'].baz)", inputs),
            "null null")


class TestFactory(unittest.TestCase):
    def test_factory(self):
        f = cwltool.factory.Factory()
        echo = f.make("tests/echo.cwl")
        self.assertEqual(echo(inp="foo"), {"out": "foo\n"})

if __name__ == '__main__':
    unittest.main()
