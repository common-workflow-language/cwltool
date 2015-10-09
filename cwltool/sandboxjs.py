import subprocess
import json
import threading

class JavascriptException(Exception):
    pass

def execjs(js, jslib):
    nodejs = subprocess.Popen(["nodejs"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    fn = "\"use strict\";%s\n(function()%s)()" % (jslib, js if isinstance(js, basestring) and len(js) > 1 and js[0] == '{' else ("{return (%s);}" % js))
    script = "console.log(JSON.stringify(require(\"vm\").runInNewContext(%s, {})))" % json.dumps(fn)

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

    if stderrdata.strip() or nodejs.returncode != 0:
        raise JavascriptException(script + "\n" + stderrdata)
    else:
        return json.loads(stdoutdata)

class SubstitutionError(Exception):
    pass

def scanner(scan):
    DEFAULT = 0
    DOLLAR = 1
    PAREN = 2
    BRACE = 3
    SINGLE_QUOTE = 4
    DOUBLE_QUOTE = 5

    i = 0
    stack = [DEFAULT]
    start = 0
    while i < len(scan):
        state = stack[-1]
        c = scan[i]

        if c == '\\':
            return [i, i+2]
        elif state == DEFAULT:
            if c == '$':
                stack.append(DOLLAR)
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
        elif state == DOUBLE_QUOTE:
            if c == '"':
                stack.pop()
        i += 1

    if len(stack) > 1:
        raise SubstitutionError("Substitution error, unfinished block starting at position {}: {}".format(start, scan[start:]))
    else:
        return None

def interpolate(scan, jslib):
    parts = []
    w = scanner(scan)
    while w:
        parts.append(scan[0:w[0]])
        if scan[w[0]] == '$':
            e = execjs(scan[w[0]+1:w[1]], jslib)
        elif scan[w[0]] == '\\':
            e = scan[w[1]-1]

        if w[0] == 0 and w[1] == len(scan):
            return e

        parts.append(json.dumps(e))
        scan = scan[w[1]:]
        w = scanner(scan)
    parts.append(scan)
    return ''.join(parts)
