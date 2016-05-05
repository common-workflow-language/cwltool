#!/usr/bin/env python

import argparse
import json
import os
import subprocess
import sys
import shutil
import tempfile
import yaml
import yaml.scanner
import pipes
import logging
import schema_salad.ref_resolver
from typing import Any, Union

_logger = logging.getLogger("cwltest")
_logger.addHandler(logging.StreamHandler())
_logger.setLevel(logging.INFO)

UNSUPPORTED_FEATURE = 33

class CompareFail(Exception):
    pass


def compare(a, b):  # type: (Any, Any) -> bool
    try:
        if isinstance(a, dict):
            if a.get("class") == "File":
                if not (b["path"].endswith("/" + a["path"]) or ("/" not in b["path"] and a["path"] == b["path"])):
                    raise CompareFail(u"%s does not end with %s" %(b["path"], a["path"]))
                # ignore empty collections
                b = {k: v for k, v in b.iteritems()
                     if not isinstance(v, (list, dict)) or len(v) > 0}
            if len(a) != len(b):
                raise CompareFail(u"expected %s\ngot %s" % (json.dumps(a, indent=4, sort_keys=True), json.dumps(b, indent=4, sort_keys=True)))
            for c in a:
                if a.get("class") != "File" or c != "path":
                    if c not in b:
                        raise CompareFail(u"%s not in %s" % (c, b))
                    if not compare(a[c], b[c]):
                        return False
            return True
        elif isinstance(a, list):
            if len(a) != len(b):
                raise CompareFail(u"expected %s\ngot %s" % (json.dumps(a, indent=4, sort_keys=True), json.dumps(b, indent=4, sort_keys=True)))
            for c in xrange(0, len(a)):
                if not compare(a[c], b[c]):
                    return False
            return True
        else:
            if a != b:
                raise CompareFail(u"%s != %s" % (a, b))
            else:
                return True
    except Exception as e:
        raise CompareFail(str(e))


def run_test(args, i, t):  # type: (argparse.Namespace, Any, Dict[str,str]) -> int
    out = {}  # type: Dict[str,Any]
    outdir = None
    try:
        if "output" in t:
            test_command = [args.tool]
            # Add prefixes if running on MacOSX so that boot2docker writes to /Users
            if 'darwin' in sys.platform:
                outdir = tempfile.mkdtemp(prefix=os.path.abspath(os.path.curdir))
                test_command.extend(["--tmp-outdir-prefix={}".format(outdir), "--tmpdir-prefix={}".format(outdir)])
            else:
                outdir = tempfile.mkdtemp()
            test_command.extend(["--outdir={}".format(outdir),
                                 "--quiet",
                                 t["tool"],
                                 t["job"]])
            outstr = subprocess.check_output(test_command)
            out = {"output": json.loads(outstr)}
        else:
            test_command = [args.tool,
                            "--conformance-test",
                            "--basedir=" + args.basedir,
                            "--no-container",
                            "--quiet",
                            t["tool"],
                            t["job"]]

            outstr = subprocess.check_output(test_command)
            out = yaml.load(outstr)
            if not isinstance(out, dict):
                raise ValueError("Non-dict value parsed from output string.")
    except ValueError as v:
        _logger.error(str(v))
        _logger.error(outstr)
    except subprocess.CalledProcessError as err:
        if err.returncode == UNSUPPORTED_FEATURE:
            return UNSUPPORTED_FEATURE
        else:
            _logger.error(u"""Test failed: %s""", " ".join([pipes.quote(tc) for tc in test_command]))
            _logger.error(t.get("doc"))
            _logger.error("Returned non-zero")
            return 1
    except yaml.scanner.ScannerError as e:
        _logger.error(u"""Test failed: %s""", " ".join([pipes.quote(tc) for tc in test_command]))
        _logger.error(outstr)
        _logger.error(u"Parse error %s", str(e))

    pwd = os.path.abspath(os.path.dirname(t["job"]))
    # t["args"] = map(lambda x: x.replace("$PWD", pwd), t["args"])
    # if "stdin" in t:
    #     t["stdin"] = t["stdin"].replace("$PWD", pwd)

    failed = False
    if "output" in t:
        checkkeys = ["output"]
    else:
        checkkeys = ["args", "stdin", "stdout", "createfiles"]

    for key in checkkeys:
        try:
            compare(t.get(key), out.get(key))
        except CompareFail as ex:
            _logger.warn(u"""Test failed: %s""", " ".join([pipes.quote(tc) for tc in test_command]))
            _logger.warn(t.get("doc"))
            _logger.warn(u"%s expected %s\n got %s", key,
                                                            json.dumps(t.get(key), indent=4, sort_keys=True),
                                                            json.dumps(out.get(key), indent=4, sort_keys=True))
            _logger.warn(u"Compare failure %s", ex)
            failed = True

    if outdir:
        shutil.rmtree(outdir, True)  # type: ignore
        # Weird AnyStr != basestring issue

    if failed:
        return 1
    else:
        return 0


def main():  # type: () -> int
    parser = argparse.ArgumentParser(description='Compliance tests for cwltool')
    parser.add_argument("--test", type=str, help="YAML file describing test cases", required=True)
    parser.add_argument("--basedir", type=str, help="Basedir to use for tests", default=".")
    parser.add_argument("-l", action="store_true", help="List tests then exit")
    parser.add_argument("-n", type=str, default=None, help="Run a specific tests, format is 1,3-6,9")
    parser.add_argument("--tool", type=str, default="cwl-runner",
                        help="CWL runner executable to use (default 'cwl-runner'")
    parser.add_argument("--only-tools", action="store_true", help="Only test tools")

    args = parser.parse_args()

    if not args.test:
        parser.print_help()
        return 1

    with open(args.test) as f:
        tests = yaml.load(f)

    failures = 0
    unsupported = 0

    if args.only_tools:
        alltests = tests
        tests = []
        for t in alltests:
            loader = schema_salad.ref_resolver.Loader({"id": "@id"})
            cwl = loader.resolve_ref(t["tool"])[0]
            if isinstance(cwl, dict):
                if cwl["class"] == "CommandLineTool":
                    tests.append(t)
            else:
                raise Exception("Unexpected code path.")

    if args.l:
        for i, t in enumerate(tests):
            print u"[%i] %s" % (i+1, t["doc"].strip())
        return 0

    if args.n is not None:
        ntest = []
        for s in args.n.split(","):
            sp = s.split("-")
            if len(sp) == 2:
                ntest.extend(range(int(sp[0])-1, int(sp[1])))
            else:
                ntest.append(int(s)-1)
    else:
        ntest = range(0, len(tests))

    for i in ntest:
        t = tests[i]
        sys.stderr.write("\rTest [%i/%i] " % (i+1, len(tests)))
        sys.stderr.flush()
        rt = run_test(args, i, t)
        if rt == 1:
            failures += 1
        elif rt == UNSUPPORTED_FEATURE:
            unsupported += 1

    if failures == 0 and unsupported == 0:
         _logger.info("All tests passed")
         return 0
    else:
        _logger.warn("%i failures, %i unsupported features", failures, unsupported)
        return 1


if __name__ == "__main__":
    sys.exit(main())
