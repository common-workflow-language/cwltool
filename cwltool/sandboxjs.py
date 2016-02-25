import subprocess
import json
import threading
import errno

class JavascriptException(Exception):
    pass

def execjs(js, jslib):
    nodejs = None
    trynodes = (["xnodejs"], ["node"], ["docker", "run",
                                       "--attach=STDIN", "--attach=STDOUT", "--attach=STDERR",
                                       "--interactive",
                                       "--rm",
                                       "node:slim"])
    for n in trynodes:
        try:
            nodejs = subprocess.Popen(n, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            break
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise

    if nodejs is None:
        raise JavascriptException("cwltool requires Node.js engine to evaluate Javascript expressions, but couldn't find it.  Tried %s" % (trynodes,))


    fn = "\"use strict\";%s\n(function()%s)()" % (jslib, js if isinstance(js, basestring) and len(js) > 1 and js[0] == '{' else ("{return (%s);}" % js))
    script = "console.log(JSON.stringify(require(\"vm\").runInNewContext(%s, {})));\n" % json.dumps(fn)

    def term():
        try:
            nodejs.terminate()
        except OSError:
            pass

    # Time out after 5 seconds
    tm = threading.Timer(5, term)
    tm.start()

    stdoutdata, stderrdata = nodejs.communicate(script)
    tm.cancel()

    if nodejs.returncode != 0:
        raise JavascriptException("Returncode was: %s\nscript was: %s\nstdout was: '%s'\nstderr was: '%s'\n" % (nodejs.returncode, script, stdoutdata, stderrdata))
    else:
        try:
            return json.loads(stdoutdata)
        except ValueError:
            raise JavascriptException("Returncode was: %s\nscript was: %s\nstdout was: '%s'\nstderr was: '%s'\n" % (nodejs.returncode, script, stdoutdata, stderrdata))

class SubstitutionError(Exception):
    pass

def scanner(scan):
    DEFAULT = 0
    DOLLAR = 1
    PAREN = 2
    BRACE = 3
    SINGLE_QUOTE = 4
    DOUBLE_QUOTE = 5
    BACKSLASH = 6

    i = 0
    stack = [DEFAULT]
    start = 0
    while i < len(scan):
        state = stack[-1]
        c = scan[i]

        if state == DEFAULT:
            if c == '$':
                stack.append(DOLLAR)
            elif c == '\\':
                stack.append(BACKSLASH)
        elif state == BACKSLASH:
            stack.pop()
            if stack[-1] == DEFAULT:
                return [i-1, i+1]
        elif state == DOLLAR:
            if c == '(':
                start = i-1
                stack.append(PAREN)
            elif c == '{':
                start = i-1
                stack.append(BRACE)
        elif state == PAREN:
            if c == '(':
                stack.append(PAREN)
            elif c == ')':
                stack.pop()
                if stack[-1] == DOLLAR:
                    return [start, i+1]
            elif c == "'":
                stack.append(SINGLE_QUOTE)
            elif c == '"':
                stack.append(DOUBLE_QUOTE)
        elif state == BRACE:
            if c == '{':
                stack.append(BRACE)
            elif c == '}':
                stack.pop()
                if stack[-1] == DOLLAR:
                    return [start, i+1]
            elif c == "'":
                stack.append(SINGLE_QUOTE)
            elif c == '"':
                stack.append(DOUBLE_QUOTE)
        elif state == SINGLE_QUOTE:
            if c == "'":
                stack.pop()
            elif c == '\\':
                stack.append(BACKSLASH)
        elif state == DOUBLE_QUOTE:
            if c == '"':
                stack.pop()
            elif c == '\\':
                stack.append(BACKSLASH)
        i += 1

    if len(stack) > 1:
        raise SubstitutionError("Substitution error, unfinished block starting at position {}: {}".format(start, scan[start:]))
    else:
        return None


def interpolate(scan, jslib):
    scan = scan.strip()
    parts = []
    w = scanner(scan)
    while w:
        parts.append(scan[0:w[0]])

        if scan[w[0]] == '$':
            e = execjs(scan[w[0]+1:w[1]], jslib)
            if w[0] == 0 and w[1] == len(scan):
                return e
            leaf = json.dumps(e, sort_keys=True)
            if leaf[0] == '"':
                leaf = leaf[1:-1]
            parts.append(leaf)
        elif scan[w[0]] == '\\':
            e = scan[w[1]-1]
            parts.append(e)

        scan = scan[w[1]:]
        w = scanner(scan)
    parts.append(scan)
    return ''.join(parts)
