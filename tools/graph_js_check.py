#!/usr/bin/env python3
"""Grep gate for the graph view's shipped sources (Borges, 2026-11-25; rules R1-R7 of F65).

Refuses any file under viewer/graph/ that contains one of the tokens that would let a data string become markup,
code or an address. A file under a directory named `test` is not shipped (the builder's copy rule) and is not
read; the run says how many files it skipped that way.

CONTRACT
 G1 Every file under DIR (default: viewer/graph next to this tool's repo), except under a directory named
    `test` or `__pycache__`, is read as UTF-8 (undecodable bytes are replaced, never skipped) and checked.
 G2 In ANY file these are refused, matched case-insensitively and tolerant of whitespace where code allows it:
    innerHTML, outerHTML, insertAdjacentHTML, `document . write`, DOMParser, createContextualFragment,
    createElementNS, `eval (`, `new  Function`, a bare `Function (`, `import (`, setTimeout / setInterval whose first
    argument is a string literal, and a PROTOCOL-RELATIVE string literal (a quote or backtick, optional spaces, then
    `//`); in .html also an UNQUOTED attribute value that starts with `//` (`src=//host/x.js`, `href=//h`).
 G2b URL schemes `http:` `https:` `javascript:` `data:` `blob:` `ws:` `wss:` `file:`, in any letter case, by file
    type. In .js / .mjs a small scanner reads the file and a scheme counts ONLY inside a string or template
    literal (a `//` or block comment is skipped; an object key or identifier followed by `:`, as in `data: null`,
    is code and is clean); the protocol-relative test is made on the same literals, so a `//` comment, even one
    after a closing quote, is not one. In .css and .html a scheme is refused anywhere. In .md (never shipped) schemes
    are not checked; every other check applies to .md as to any file.
 G3 In a .html file these are also refused: an `on...=` attribute, `<style`, and `style=`.
 G3b In a .css file these are also refused: `@import` and `url(` with anything.
 G3c In a shipped file (.js .mjs .html) an import specifier (`from '..'`, `import '..'`, `import('..')`, and a
    <script>/<link> src or href) that resolves, from the file's own folder, into a path with a `test` segment is
    refused (`import of a test path`): a shipped file may not reach around the skip rule into what is not shipped.
 G4 Each refusal prints `REFUSED path:line TOKEN`. The run ends with
    `N files checked, M refused, S skipped as test files`.
 G5 Exit 0 only if at least one file was checked and none refused. Exit 1 on a refusal, or on `CHECKED NOTHING`
    (no file to read: a gate over nothing must not pass). Exit 2 usage / DIR is not a directory.
 G6 A normal run first runs its own self-test and refuses (exit 4) if it fails. --selftest plants each token
    and each variant in a temporary tree and expects its refusal, clean files to pass (a JS file whose only `//` are
    comments included), a token under test/ to be ignored and counted, and an empty tree to be CHECKED NOTHING.
 LIMIT: substring and line-pattern checks over text. A token split across lines or built from pieces is not seen,
 nor is `(0, eval)(s)`; that is why the engine's own boundary test also forbids the APIs by name in each file.
 Comments count: a comment that names a forbidden token is refused too (the .js scheme and protocol-relative
 checks are the exception: they read literals only, so a scheme in a JS comment is not seen). The scanner does not
 know regex literals or `${}` nesting. KNOWN MISSES, each asserted as a miss by the self-test (MISSES); the list is
 NOT exhaustive, it holds the misses we have found and nothing more: a quote
 inside a regex literal before a URL; `//` inside a regex character class, which hides the rest of that line;
 `/*` inside a regex character class, which hides the REST OF THE FILE until a `*/`; a template literal nested
 inside `${}`; backslash-u and backslash-x escapes inside a literal, and String.fromCharCode; piece-building by concatenation; in html, an attribute value that starts on the line after `href=` (the check
 is per line), an entity-encoded value (`href=&#47;&#47;h`), and an unquoted `//` value in a `.htm` or `.svg` file
 (that check reads `.html` only). An import specifier built at run time is not resolved; a dynamic
 `import (` is refused outright instead. A `__pycache__` folder is skipped without a count.

usage: graph_js_check.py [DIR]
       graph_js_check.py --selftest
"""
import os, posixpath, re, sys, tempfile

I = re.I
# (token the refusal names, pattern): every one is matched case-insensitively, per line, in ANY file
ANY_RE = [
    ("innerHTML", re.compile(r"innerHTML", I)),
    ("outerHTML", re.compile(r"outerHTML", I)),
    ("insertAdjacentHTML", re.compile(r"insertAdjacentHTML", I)),
    ("document.write", re.compile(r"document\s*\.\s*write", I)),
    ("DOMParser", re.compile(r"DOMParser", I)),
    ("createContextualFragment", re.compile(r"createContextualFragment", I)),
    ("createElementNS", re.compile(r"createElementNS", I)),
    ("setHTMLUnsafe", re.compile(r"setHTMLUnsafe", I)),
    ("parseHTMLUnsafe", re.compile(r"parseHTMLUnsafe", I)),
    ("srcdoc", re.compile(r"srcdoc", I)),
    ("Worker(", re.compile(r"\bWorker\s*\(", I)),
    ("importScripts", re.compile(r"importScripts", I)),
    ("eval(", re.compile(r"eval\s*\(", I)),
    ("new Function", re.compile(r"new\s+Function", I)),
    ("Function(", re.compile(r"\bFunction\s*\(", I)),
    ("import(", re.compile(r"\bimport\s*\(", I)),
    ("setTimeout/setInterval with a string", re.compile(r"set(?:Timeout|Interval)\s*\(\s*[\"'`]", I)),
]
# URL schemes, any letter case. In .css and .html they are refused anywhere in the text; in .js / .mjs only inside a
# string or template literal (a key such as `data: null` is code); in .md (never shipped) not checked at all.
SCHEME_RE = [
    ("http:", re.compile(r"\bhttp:", I)),
    ("https:", re.compile(r"\bhttps:", I)),
    ("javascript:", re.compile(r"\bjavascript:", I)),
    ("data:", re.compile(r"\bdata:", I)),
    ("blob:", re.compile(r"\bblob:", I)),
    ("ws:", re.compile(r"\bws:", I)),
    ("wss:", re.compile(r"\bwss:", I)),
    ("file:", re.compile(r"\bfile:", I)),
]
HTML_RE = [("on...= attribute", re.compile(r"<[^>]*\son[a-z]+\s*=", I)),
           ("<style", re.compile(r"<style", I)),
           ("style=", re.compile(r"\sstyle\s*=", I))]
CSS_RE = [("@import", re.compile(r"@import", I)),
          ("url(", re.compile(r"url\s*\(", I))]
PROTO = "protocol-relative URL"
PROTO_RE = re.compile(r"[\"'`]\s*//")            # for files that are not scanned as JS (.html, .css, .md ...)
UNQUOTED_RE = re.compile(r"[\w-]\s*=\s*//")      # .html: an unquoted attribute value that starts with // (src=//host/x.js)
TESTIMP = "import of a test path"
IMPORT_RES = [re.compile(r"""\bfrom\s*["']([^"']+)["']"""),
              re.compile(r"""\bimport\s*["']([^"']+)["']"""),
              re.compile(r"""\bimport\s*\(\s*["']([^"']+)["']""")]
SRC_RE = re.compile(r"""\b(?:src|href)\s*=\s*["']([^"']+)["']""", I)
JS_EXT = (".js", ".mjs")
MD_EXT = (".md",)
SHIP_IMPORT_EXT = (".js", ".mjs", ".html")
SKIP_DIRS = {"test", "__pycache__"}
TEST_DIR = "test"        # the builder's copy rule: a path with a directory segment named exactly this is not shipped


def default_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "viewer", "graph")


def files_under(d, skipped=None):
    """Yield every file to check. A directory named `test` is pruned; the files in it are counted into
    skipped[0] when a list is given, so the skip is never silent. (`__pycache__` is pruned without a count.)"""
    for base, dirs, names in os.walk(d):
        keep = []
        for x in sorted(dirs):
            if x == TEST_DIR and skipped is not None:
                skipped[0] += sum(len(fs) for _, _, fs in os.walk(os.path.join(base, x)))
            if x not in SKIP_DIRS:
                keep.append(x)
        dirs[:] = keep
        for n in sorted(names):
            yield os.path.join(base, n)


def js_literals(text):
    """[(line, content)] for every string and template literal in JS text, `line` being the line it OPENS on and
    `content` what is between its quotes. Line and block comments are skipped, so `const b = 'x'; // note` (a
    closing quote then a comment) opens nothing. An unterminated ' or " literal ends at the end of its line."""
    out, i, n, line, state = [], 0, len(text), 1, None      # state: None | "//" | "/*" | the open quote
    start, begin = 0, 0
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            if state in ("'", '"'):
                out.append((begin, text[start:i])); state = None
            elif state == "//":
                state = None
            i += 1
        elif state is None:
            if text.startswith("//", i):
                state = "//"; i += 2
            elif text.startswith("/*", i):
                state = "/*"; i += 2
            elif c in "'\"`":
                state = c; i += 1; start = i; begin = line
            else:
                i += 1
        elif state == "/*":
            if text.startswith("*/", i):
                state = None; i += 2
            else:
                i += 1
        elif state == "//":
            i += 1
        elif c == "\\":
            if i + 1 < n and text[i + 1] == "\n":
                line += 1
            i += 2
        elif c == state:
            out.append((begin, text[start:i])); state = None; i += 1
        else:
            i += 1
    if state in ("'", '"', "`"):
        out.append((begin, text[start:]))
    return out


def js_literal_hits(text):
    """Refusals found inside JS literals: a URL scheme anywhere in the content, or a protocol-relative start."""
    hits = []
    for ln, content in js_literals(text):
        for name, rx in SCHEME_RE:
            m = rx.search(content)
            if m:
                hits.append((ln + content.count("\n", 0, m.start()), name))
        if content.lstrip(" \t").startswith("//"):
            hits.append((ln, PROTO))
    return hits


def into_test(rel, spec):
    """True if the specifier, resolved from the folder of the file at `rel`, has a segment named `test`."""
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(rel.replace(os.sep, "/")), spec))
    return TEST_DIR in joined.split("/") or TEST_DIR in spec.split("/")


def check_file(path, rel=None):
    """Return [(line, token)] for every refusal in one file. `rel` is the path under DIR (used to resolve imports)."""
    rel = rel or os.path.basename(path)
    text = open(path, "rb").read().decode("utf8", errors="replace")
    hits = []
    for i, line in enumerate(text.split("\n"), 1):
        for name, rx in ANY_RE:
            if rx.search(line):
                hits.append((i, name))
        if not path.endswith(JS_EXT + MD_EXT):          # .css .html and anything else: schemes anywhere
            for name, rx in SCHEME_RE:
                if rx.search(line):
                    hits.append((i, name))
        if path.endswith(".html"):
            for name, rx in HTML_RE:
                if rx.search(line):
                    hits.append((i, name))
        if path.endswith(".css"):
            for name, rx in CSS_RE:
                if rx.search(line):
                    hits.append((i, name))
        if not path.endswith(JS_EXT) and PROTO_RE.search(line):
            hits.append((i, PROTO))
        if path.endswith(".html") and UNQUOTED_RE.search(line):
            hits.append((i, PROTO))
    if path.endswith(JS_EXT):
        hits.extend(js_literal_hits(text))
    if path.endswith(SHIP_IMPORT_EXT):
        for rx in IMPORT_RES + ([SRC_RE] if path.endswith(".html") else []):
            for m in rx.finditer(text):
                if into_test(rel, m.group(1)):
                    hits.append((text.count("\n", 0, m.start()) + 1, TESTIMP))
    return sorted(set(hits))


def run(d, out):
    n = refused = 0
    skipped = [0]
    for p in files_under(d, skipped):
        n += 1
        for line, tok in check_file(p, os.path.relpath(p, d)):
            refused += 1
            print("REFUSED %s:%d %s" % (os.path.relpath(p, d), line, tok), file=out)
    if n == 0:
        print("CHECKED NOTHING: no file under %s (%d skipped as test files)" % (d, skipped[0]), file=out)
        return 1
    print("%d files checked, %d refused, %d skipped as test files" % (n, refused, skipped[0]), file=out)
    return 1 if refused else 0


# literals, written here and never read back from the tool: (file name, planted text, token the refusal must name)
PLANTS = [
    ("a.js", "x.innerHTML = s;", "innerHTML"),
    ("a.js", "x.outerHTML = s;", "outerHTML"),
    ("a.js", "x.insertAdjacentHTML('beforeend', s);", "insertAdjacentHTML"),
    ("a.js", "document.write(s);", "document.write"),
    ("a.js", "new DOMParser();", "DOMParser"),
    ("a.js", "r.createContextualFragment(s);", "createContextualFragment"),
    ("a.js", "eval(s);", "eval("),
    ("a.js", "const f = new Function('return 1');", "new Function"),
    ("a.js", "const u = 'http://example.org/';", "http:"),
    ("a.js", "const u = 'https://example.org/';", "https:"),
    ("a.js", "setTimeout('go()', 10);", "setTimeout/setInterval with a string"),
    ("a.js", "setInterval(\"go()\", 10);", "setTimeout/setInterval with a string"),
    ("a.css", "a { background: url(http://example.org/x.png); }", "http:"),
    ("p.html", "<button onclick=\"go()\">x</button>", "on...= attribute"),
    ("p.html", "<div onmouseover = \"go()\">x</div>", "on...= attribute"),
    ("p.html", "<style>a{}</style>", "<style"),
    ("p.html", "<div style=\"color:red\">x</div>", "style="),
    ("sub/deep/b.js", "x.innerHTML = s;", "innerHTML"),
    # round 2 (F6): whitespace and letter case do not defeat a token
    ("a.js", "eval (s);", "eval("),
    ("a.js", "EVAL\t(s);", "eval("),
    ("a.js", "const f = new  Function('return 1');", "new Function"),
    ("a.js", "const f = NEW FUNCTION('x');", "new Function"),
    ("a.js", "const f = Function('return 1');", "Function("),
    ("a.js", "setTimeout ( `go()`, 10);", "setTimeout/setInterval with a string"),
    ("a.js", "SETINTERVAL (  \"go()\", 10);", "setTimeout/setInterval with a string"),
    ("a.js", "const m = import ('./x.js');", "import("),
    ("a.js", "document . write(s);", "document.write"),
    ("a.js", "x.INNERHTML = s;", "innerHTML"),
    ("a.js", "d.createElementNS(ns, 'svg');", "createElementNS"),
    # round 3: the contract's remaining sinks
    ("a.js", "e.setHTMLUnsafe(s);", "setHTMLUnsafe"),
    ("a.js", "Document.parseHTMLUnsafe(s);", "parseHTMLUnsafe"),
    ("a.js", "f.srcdoc = s;", "srcdoc"),
    ("a.js", "f.SRCDOC = s;", "srcdoc"),
    ("a.html", "<iframe srcdoc=\"x\"></iframe>", "srcdoc"),
    ("a.js", "const w = new Worker(u);", "Worker("),
    ("a.js", "const w = new Worker (u);", "Worker("),
    ("a.js", "importScripts(u);", "importScripts"),
    ("a.js", "const u = 'HTTPS://example.org/';", "https:"),
    ("a.js", "const u = 'Http://example.org/';", "http:"),
    ("a.js", "const u = 'JAVASCRIPT:alert(1)';", "javascript:"),
    ("a.js", "const u = 'Data:text/html,x';", "data:"),
    ("a.js", "const u = `javascript:${x}`;", "javascript:"),
    ("a.js", "const u = \"HTTPS://h\";", "https:"),
    ("a.html", "<a href=\"data:x\">x</a>", "data:"),
    ("a.js", "const u = 'BLOB:null/x';", "blob:"),
    ("a.js", "const u = 'ws://host/x';", "ws:"),
    ("a.js", "const u = 'WSS://host/x';", "wss:"),
    ("a.js", "const u = 'FILE:///etc/x';", "file:"),
    # a protocol-relative string literal (an opening quote or backtick, optional spaces, then //)
    ("a.js", "const u = '//host/x.js';", "protocol-relative URL"),
    ("a.js", "const u = \"  //host/x.js\";", "protocol-relative URL"),
    ("a.js", "const u = `//host/x.js`;", "protocol-relative URL"),
    ("a.html", "<script src=\"//host/x.js\"></script>", "protocol-relative URL"),
    # G4a: an UNQUOTED html attribute value that starts with //
    ("a.html", "<script src=//host/x.js></script>", "protocol-relative URL"),
    ("a.html", "<a href=//h>x</a>", "protocol-relative URL"),
    ("a.html", "<a href = //h>x</a>", "protocol-relative URL"),
    # css: @import and url( with anything
    ("a.css", "@import url(//host/a.css);", "@import"),
    ("a.css", "@IMPORT 'x.css';", "@import"),
    ("a.css", "a { background: url(x.png); }", "url("),
    ("a.css", "a { background: URL (x.png); }", "url("),
    # F7: a shipped file that reaches into a test path
    ("a.js", "import { x } from './test/x.js';", "import of a test path"),
    ("sub/b.js", "import '../test/y.js';", "import of a test path"),
    ("sub/c.js", "export * from \"./deep/../test/z.js\";", "import of a test path"),
    ("a.html", "<script type=\"module\" src=\"./test/page.js\"></script>", "import of a test path"),
]
CLEAN = [
    ("ok.js", "el.style.transform = 'none'; setTimeout(() => go(), 10); const s = el.textContent;"),
    ("ok.html", "<!doctype html><script type=\"module\" src=\"app.js\"></script><link rel=\"stylesheet\" href=\"a.css\"><p class=\"x\">done</p>"),
    ("ok.css", ".a { color: red; }"),
    ("a.js", "x.style='nothing here'; // style= in a .js is not a refusal"),
    # F6: a JS file whose only // are comments (after a closing quote too) is not a protocol-relative URL
    ("c.js", "const a = 1; // a line comment\nconst b = 'x';  // after a closing quote\nconst c = \"y\" // and again\nconst d = a / 2 / 3; /* it's a block comment // not a URL */\nconst e = { rows: 1, profile: 2, tests: 3 };"),
    # URL schemes in .js count only inside a string or template literal: a key or identifier then ':' is code
    ("e.js", "const s = { data: null, file: 1, ws: 2, blob: 3 };\nconst t = (a) ? data : 0; // see https://example.org/ in a comment"),
    # .md never ships and is not checked for schemes
    ("e.md", "data: any\nin this file: a node\nsee https://example.org/ and javascript: here"),
    # F7: a shipped file may import a sibling that merely has `test` inside a name
    ("d.js", "import { q } from './contest/q.js'; import { r } from './latest.js';"),
    # an html attribute that merely contains // later in its value, or a single slash, is not protocol-relative
    ("ok2.html", "<a href=/docs/x.html>x</a><a href=\"a//b\">y</a>"),
]
# KNOWN MISSES (not exhaustive): each of these hides a refusable token from the scanner TODAY (the LIMIT text lists them).
# The self-test asserts every one is NOT refused, so a change that starts catching one fails here and the list
# must be edited on purpose: (what is missed, file name, text; every line below carries a scheme or `//` that a
# perfect reader would refuse).
MISSES = [
    ("a quote inside a regex literal before a URL", "m1.js", "const r = /'/; const u = 'https://h/x';"),
    ("`//` inside a regex character class (hides the rest of the line)", "m2.js", "const r = /[//]/; const u = 'https://h/x';"),
    ("`/*` inside a regex character class (hides the REST OF THE FILE until a `*/`)", "m3.js", "const r = /[/*]/;\nconst u = 'https://h/x';\nconst v = 'javascript:x';"),
    ("a template literal nested inside `${}`", "m4.js", "const u = `${ `https://h/x` }`;"),
    ("a \\x escape", "m5.js", "const u = 'h\\x74tps://h/x';"),
    ("a \\u escape", "m6.js", "const u = '\\u0068ttps://h/x';"),
    ("String.fromCharCode", "m7.js", "const u = String.fromCharCode(104, 116, 116, 112, 115, 58);"),
    ("piece-building by concatenation", "m8.js", "const u = 'java' + 'script:' + x;"),
    ("html: an attribute value on the line after `href=` (the check is per line)", "m9.html", "<a href=\n//h>x</a>"),
    ("html: an entity-encoded value", "m10.html", "<a href=&#47;&#47;h>x</a>"),
    ("html: an unquoted `//` value in a `.htm` file (the check reads `.html` only)", "m11.htm", "<a href=//h>x</a>"),
]


def selftest():
    import io
    ok, notes = True, []
    for name, text, token in PLANTS:
        d = tempfile.mkdtemp()
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(text + "\n")
        buf = io.StringIO()
        rc = run(d, buf)
        good = rc == 1 and ("REFUSED " + name + ":1 " + token) in buf.getvalue()
        if not good:
            ok = False
            notes.append("not refused: %s in %s -> rc %d %r" % (token, name, rc, buf.getvalue()))
    d = tempfile.mkdtemp()
    for name, text in CLEAN:
        open(os.path.join(d, name), "w").write(text + "\n")
    buf = io.StringIO()
    rc = run(d, buf)
    if rc != 0 or ("%d files checked, 0 refused, 0 skipped as test files" % len(CLEAN)) not in buf.getvalue():
        ok = False
        notes.append("clean files were refused or miscounted: " + buf.getvalue())
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "engine", "test", "deep"))
    open(os.path.join(d, "engine", "test", "t.js"), "w").write("x.innerHTML = 1; fetch('http://x')\n")
    open(os.path.join(d, "engine", "test", "deep", "u.js"), "w").write("eval(s)\n")
    open(os.path.join(d, "engine", "i.js"), "w").write("export const a = 1;\n")
    buf = io.StringIO()
    if run(d, buf) != 0 or "1 files checked, 0 refused, 2 skipped as test files" not in buf.getvalue():
        ok = False
        notes.append("a token under test/ was read, or the skipped files were not counted aloud: " + buf.getvalue())
    d = tempfile.mkdtemp()
    buf = io.StringIO()
    if run(d, buf) != 1 or "CHECKED NOTHING" not in buf.getvalue():
        ok = False
        notes.append("an empty tree was not CHECKED NOTHING")
    for what, name, text in MISSES:           # documented misses: each is NOT refused today
        d = tempfile.mkdtemp()
        open(os.path.join(d, name), "w").write(text + "\n")
        buf = io.StringIO()
        if run(d, buf) != 0:
            ok = False
            notes.append("documented miss is now refused (edit MISSES and the LIMIT text on purpose): " + what + " -> " + buf.getvalue())
    for n in notes:
        print(n)
    print("SELFTEST " + ("PASS: %d planted tokens each refused, clean files pass, test/ is not read, an empty tree is CHECKED NOTHING, %d documented misses are still misses" % (len(PLANTS), len(MISSES)) if ok else "FAIL"))
    return 0 if ok else 4


def selftest_quiet():
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        return selftest()


def main(a):
    if a[1:] == ["--selftest"]:
        return selftest()
    if len(a) > 2 or (len(a) == 2 and a[1].startswith("-")):
        print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
        return 2
    d = a[1] if len(a) == 2 else default_dir()
    if not os.path.isdir(d):
        print("not a directory: " + d, file=sys.stderr)
        return 2
    if selftest_quiet() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    return run(d, sys.stdout)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
